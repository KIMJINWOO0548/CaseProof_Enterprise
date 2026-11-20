"""CP2/CP6 acceptance on disposable SQLite with independent outcome checks."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Barrier

import pytest
from sqlalchemy import event, select

from service import models_v1 as m
from service.api.errors import DomainError
from service.commands import execute_command
from service.db import make_engine, session_factory
from service.recovery import backup_database, file_sha256, reactivate_reviewed_actors, restore_database
from service.workspace import create_workspace_app
from tests.v1.helpers import command, dump, setup
from tests.v1.test_http import request as http_request


def test_concurrent_same_intent_has_one_commit_on_two_connections(tmp_path):
    factory, actors, body = setup(tmp_path)
    engine = factory.kw['bind']
    request = command(body, key='cp6-concurrent-create')
    barrier = Barrier(2, timeout=15)
    connections = []

    def rendezvous(connection, _record, _proxy):
        connections.append(connection)
        barrier.wait()

    def send():
        try:
            return execute_command(factory, actors['analyst'], request)
        except DomainError as error:
            return error

    try:
        event.listen(engine, 'checkout', rendezvous)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [future.result(timeout=25) for future in (pool.submit(send), pool.submit(send))]
        finally:
            event.remove(engine, 'checkout', rendezvous)

        assert len(connections) == 2 and connections[0] is not connections[1]
        assert not [result.code for result in results if isinstance(result, DomainError)]
        assert sorted(result.replayed for result in results) == [False, True]
        assert [(result.status_code, result.result_revision) for result in results] == [(201, 1), (201, 1)]
        assert results[0].data == results[1].data
        assert results[0].data['status'] == 'DRAFT'
        persisted = dump(factory)
        assert {name: len(persisted['v1_' + name]) for name in (
            'change', 'change_revision', 'change_transition', 'audit_event', 'idempotency_record',
        )} == dict(change=1, change_revision=1, change_transition=1, audit_event=1, idempotency_record=1)
        assert execute_command(factory, actors['analyst'], request).data == results[0].data
        assert dump(factory) == persisted
    finally:
        engine.dispose()


class ResponseLost(Exception):
    pass


def drop_committed_response(app, expected_status):
    async def without_response(scope, receive, send):
        async def drop(message):
            if message['type'] == 'http.response.start':
                assert message['status'] == expected_status
                raise ResponseLost
            await send(message)

        await app(scope, receive, drop)

    return without_response


def auth(actor):
    return {'Authorization': 'Bearer ' + actor}


def context_for(app, actor):
    response = http_request(app, 'GET', '/api/v1/workspace', headers=auth(actor))
    assert response.status_code == 200
    return response.json()['data']['request_context']


def post(app, path, actor, key, body, context, revision=None):
    headers = auth(actor) | {'Idempotency-Key': key, 'X-CaseProof-Request-Context': context}
    if revision is not None:
        headers['X-Expected-Revision'] = str(revision)
    return http_request(app, 'POST', path, body, headers=headers)


def original_result(response, code, revision, state, *, replayed=False):
    assert response.status_code == code, response.text
    payload = response.json()
    assert (payload['result_revision'], payload['replayed']) == (revision, replayed)
    assert (payload['data']['revision'], payload['data']['status']) == (revision, state)
    return payload['data']


def check_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()['error']['code'] == code
    assert 'data' not in response.json()


def saved_approval(factory, change_id):
    """Read raw frozen bytes without using repository reconstruction or digest helpers."""
    with factory() as db:
        run = db.execute(select(m.EvaluationRun).where(m.EvaluationRun.change_id == change_id)).scalar_one()
        envelope = db.execute(select(m.ApprovalEnvelope).where(m.ApprovalEnvelope.change_id == change_id)).scalar_one()
        notes = db.execute(select(m.DecisionNote).where(m.DecisionNote.change_id == change_id)
                           .order_by(m.DecisionNote.output_revision)).scalars().all()
        snapshots = db.execute(select(m.ChangeRevision).where(m.ChangeRevision.change_id == change_id)
                               .order_by(m.ChangeRevision.revision)).scalars().all()
        transitions = db.execute(select(m.ChangeTransition).where(m.ChangeTransition.change_id == change_id)
                                 .order_by(m.ChangeTransition.revision_to)).scalars().all()
        sources = db.execute(select(m.SourceSnapshot).order_by(m.SourceSnapshot.id)).scalars().all()
        return {
            'run': (run.id, run.canonical_payload),
            'envelope': envelope.canonical_payload,
            'notes': [row.canonical_payload for row in notes],
            'snapshots': [row.canonical_payload for row in snapshots],
            'transitions': [row.canonical_payload for row in transitions],
            'sources': {row.id: row.canonical_payload for row in sources},
        }


def digest(purpose, payload):
    return hashlib.sha256(f'caseproof:{purpose}:v1\n'.encode('ascii') + payload).hexdigest()


def test_reconnect_workflow_keeps_approval_truth_and_cannot_replay_on_old_backup(tmp_path, monkeypatch, request):
    monkeypatch.setenv('CASEPROOF_DEMO_MODE', '1')
    initial, actors, body = setup(tmp_path)
    request.addfinalizer(initial.kw['bind'].dispose)
    registry = {hashlib.sha256(name.encode()).hexdigest(): {'tenant_id': actor.tenant_id, 'actor_id': actor.actor_id}
                for name, actor in actors.items()}
    app = create_workspace_app(initial, registry)
    analyst, reviewer, approver = (context_for(app, actor) for actor in ('analyst', 'reviewer', 'approver'))
    assert None not in (analyst, reviewer, approver)
    created = original_result(post(app, '/api/v1/changes', 'analyst', 'cp6-initial-create', body, analyst), 201, 1, 'DRAFT')
    identity = created['change_id']
    path = '/api/v1/changes/' + identity
    case_inputs = [{'case_id': case, 'claim_days': 30, 'case_context': {}} for case in ('case-a', 'case-b')]
    evaluation = {'suite_version_id': body['suite_version_id'], 'case_inputs': case_inputs}

    def fail_before_commit(stage):
        if stage == 'idempotency':
            raise RuntimeError('synthetic service interruption before commit')

    before = dump(initial)
    with monkeypatch.context() as injected:
        injected.setattr('service.commands.checkpoint', fail_before_commit)
        check_error(post(app, path + '/evaluation-runs', 'analyst', 'cp6-eval-request', evaluation, analyst, 1),
                    500, 'INTERNAL_ERROR')
    assert dump(initial) == before
    check_error(http_request(app, 'GET', '/api/v1/mutations/cp6-eval-request', headers=auth('analyst')), 404, 'NOT_FOUND')
    evaluated = original_result(post(app, path + '/evaluation-runs', 'analyst', 'cp6-eval-request',
                                     evaluation, analyst, 1), 201, 2, 'DRAFT')
    run = evaluated['run']
    assert (run['schema'], run['suite_version_id'], run['gate_summary']) == (
        'evaluation_run_v2', body['suite_version_id'], 'PASS')
    assert [(item['case_id'], item['verdict']) for item in run['case_results']] == [('case-a', 'PASS'), ('case-b', 'PASS')]
    original_result(post(app, path + '/submit', 'analyst', 'cp6-submit-request', {}, analyst, 2),
                    200, 3, 'PENDING_DOMAIN_REVIEW')
    domain = {'decision': 'APPROVE', 'reason': 'Domain checked both synthetic records'}
    release = {'decision': 'APPROVE', 'reason': 'Release checked both synthetic records'}
    original_result(post(app, path + '/domain-decision', 'reviewer', 'cp6-domain-request', domain, reviewer, 3),
                    200, 4, 'PENDING_RELEASE')
    with pytest.raises(ResponseLost):
        post(drop_committed_response(app, 200), path + '/release-decision', 'approver',
             'cp6-release-request', release, approver, 4)
    sealed = saved_approval(initial, identity)
    initial.kw['bind'].dispose()

    engine = make_engine('sqlite:///' + (tmp_path / 'v1.db').as_posix())
    factory = session_factory(engine)
    try:
        reconnected = create_workspace_app(factory, registry)
        assert context_for(reconnected, 'approver') == approver
        no_repeat = dump(factory)
        recovered = original_result(post(reconnected, path + '/release-decision', 'approver',
                                         'cp6-release-request', release, approver, 4),
                                    200, 5, 'APPROVED_FOR_DEMO', replayed=True)
        changed = dict(release, reason='A different synthetic release reason')
        check_error(post(reconnected, path + '/release-decision', 'approver', 'cp6-release-request',
                         changed, approver, 4), 409, 'IDEMPOTENCY_CONFLICT')
        assert dump(factory) == no_repeat
        assert recovered == json.loads(sealed['snapshots'][-1])
        assert [(json.loads(raw)['revision'], json.loads(raw)['status']) for raw in sealed['snapshots']] == [
            (1, 'DRAFT'), (2, 'DRAFT'), (3, 'PENDING_DOMAIN_REVIEW'), (4, 'PENDING_RELEASE'), (5, 'APPROVED_FOR_DEMO')]
        assert [(note['actor_id'], note['stage'], note['output_revision']) for note in map(json.loads, sealed['notes'])] == [
            ('reviewer', 'DOMAIN', 4), ('approver', 'RELEASE', 5)]
        assert [item['kind'] for item in map(json.loads, sealed['transitions'])] == [
            'CHANGE_CREATED', 'EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW', 'DOMAIN_APPROVE', 'APPROVED_FOR_DEMO']
        assert (sealed['run'][0], json.loads(sealed['run'][1])['run_config_sha256']) == (run['id'], run['run_config_sha256'])
        expected_hash = digest('approval-envelope', sealed['envelope'])

        def assert_evidence(current_app, token):
            response = http_request(current_app, 'GET', path + '/evidence', headers=auth(token))
            assert response.status_code == 200
            evidence = response.json()['data']
            assert (evidence['historical_integrity'], evidence['approved_revision'], evidence['envelope_sha256']) == (
                'VALID', 5, expected_hash)
            refs = evidence['immutable_refs']
            assert refs['run_refs'] == [{'id': run['id'], 'payload_sha256': digest('evaluation-run', sealed['run'][1])}]
            assert {ref['id']: ref['payload_sha256'] for ref in refs['source_refs']} == {
                source_id: digest('source', raw) for source_id, raw in sealed['sources'].items()}

        assert_evidence(reconnected, 'approver')
        backup, target = tmp_path / 'old-backup.db', tmp_path / 'restored.db'
        metadata = backup_database(tmp_path / 'v1.db', backup)
        newer_body = dict(body, title='A second synthetic request after the backup')
        with pytest.raises(ResponseLost):
            post(drop_committed_response(reconnected, 201), '/api/v1/changes', 'analyst', 'cp6-post-backup-intent',
                 newer_body, analyst)
        receipt = http_request(reconnected, 'GET', '/api/v1/mutations/cp6-post-backup-intent', headers=auth('analyst'))
        assert receipt.status_code == 200 and receipt.json()['original_status'] == 201
        newer_path = '/api/v1/changes/' + receipt.json()['data']['change_id']
        original_result(post(reconnected, newer_path + '/evaluation-runs', 'analyst', 'cp6-new-evaluation',
                             evaluation, analyst, 1), 201, 2, 'DRAFT')
        original_result(post(reconnected, newer_path + '/submit', 'analyst', 'cp6-new-submission', {}, analyst, 2),
                        200, 3, 'PENDING_DOMAIN_REVIEW')
        preview = http_request(reconnected, 'GET', newer_path, headers=auth('reviewer'))
        assert preview.json()['data']['status'] == 'PENDING_DOMAIN_REVIEW'
        with factory.begin() as db:
            db.get(m.Actor, ('tenant-a', 'reviewer')).roles_payload = b'["AUDITOR"]'
            db.get(m.Actor, ('tenant-a', 'approver')).enabled = False
        revoked = dump(factory)
        check_error(post(reconnected, newer_path + '/domain-decision', 'reviewer', 'cp6-revoked-decision',
                         domain, reviewer, 3), 403, 'FORBIDDEN')
        check_error(http_request(reconnected, 'GET', '/api/v1/mutations/cp6-domain-request', headers=auth('reviewer')),
                    403, 'FORBIDDEN')
        check_error(post(reconnected, path + '/release-decision', 'approver', 'cp6-release-request',
                         release, approver, 4), 401, 'UNAUTHENTICATED')
        assert dump(factory) == revoked
    finally:
        engine.dispose()

    report = restore_database(backup, target, metadata)
    assert report['authorization_state'] == 'QUARANTINED'
    restored_engine = make_engine('sqlite:///' + target.as_posix())
    restored = session_factory(restored_engine)
    try:
        quarantined = create_workspace_app(restored, registry)
        for actor in actors:
            check_error(http_request(quarantined, 'GET', '/api/v1/workspace', headers=auth(actor)), 401, 'UNAUTHENTICATED')
    finally:
        restored_engine.dispose()
    grants = [{'tenant_id': 'tenant-a', 'actor_id': actor, 'roles': [role]}
              for actor, role in [('analyst', 'ANALYST'), ('reviewer', 'AUDITOR')]]
    rotated = {hashlib.sha256(('rotated-' + grant['actor_id']).encode()).hexdigest():
               {'tenant_id': grant['tenant_id'], 'actor_id': grant['actor_id']} for grant in grants}
    reactivate_reviewed_actors(target, file_sha256(target), grants, registry, rotated, 'synthetic-review-current-roles')
    restored_engine = make_engine('sqlite:///' + target.as_posix())
    restored = session_factory(restored_engine)
    try:
        recovered_app = create_workspace_app(restored, rotated)
        restored_before = dump(restored)
        for actor in actors:
            check_error(http_request(recovered_app, 'GET', '/api/v1/workspace', headers=auth(actor)), 401, 'UNAUTHENTICATED')
        assert context_for(recovered_app, 'rotated-analyst') != analyst
        check_error(http_request(recovered_app, 'GET', '/api/v1/mutations/cp6-post-backup-intent',
                                 headers=auth('rotated-analyst')), 404, 'NOT_FOUND')
        check_error(post(recovered_app, '/api/v1/changes', 'rotated-analyst', 'cp6-post-backup-intent', newer_body,
                         analyst), 409, 'REQUEST_CONTEXT_CHANGED')
        check_error(http_request(recovered_app, 'GET', '/api/v1/mutations/cp6-domain-request', headers=auth('rotated-reviewer')),
                    403, 'FORBIDDEN')
        check_error(post(recovered_app, path + '/domain-decision', 'rotated-reviewer', 'cp6-domain-request',
                         domain, context_for(recovered_app, 'rotated-reviewer'), 3), 403, 'FORBIDDEN')
        assert saved_approval(restored, identity) == sealed
        assert_evidence(recovered_app, 'rotated-reviewer')
        assert dump(restored) == restored_before
    finally:
        restored_engine.dispose()
