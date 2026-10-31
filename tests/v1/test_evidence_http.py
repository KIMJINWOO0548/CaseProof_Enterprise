"""Evidence HTTP refs match stored canonical hashes without exposing payloads."""
import hashlib
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import select, text, update

from service import models_v1 as m
from service.api.v1 import build_router
from service.auth import DemoTokenAuthenticator
from service.domain.canonical import canonical_bytes, content_hash
from service.repositories import add_payload
from tests.v1.helpers import setup
from tests.v1.test_http import request


def fixture(tmp_path):
    factory, actors, body = setup(tmp_path)
    with factory.begin() as db:
        db.add(m.Tenant(id='tenant-b'))
        db.flush()
        db.add(m.Actor(tenant_id='tenant-b', id='outsider', enabled=True,
                       roles_payload=canonical_bytes(['AUDITOR'])))
        db.add(m.Actor(tenant_id='tenant-a', id='no-role', enabled=True,
                       roles_payload=canonical_bytes([])))
    identities = {name: (actor.tenant_id, actor.actor_id) for name, actor in actors.items()}
    identities.update(outsider=('tenant-b', 'outsider'), **{'no-role': ('tenant-a', 'no-role')})
    registry = {hashlib.sha256(name.encode()).hexdigest(): {'tenant_id': tenant, 'actor_id': actor}
                for name, (tenant, actor) in identities.items()}
    app = FastAPI()
    app.include_router(build_router(factory, DemoTokenAuthenticator(registry)))
    return app, factory, body


def post(app, path, body, actor='analyst', revision=None):
    headers = {'Authorization': 'Bearer ' + actor, 'Idempotency-Key': uuid4().hex,
               'Content-Type': 'application/json'}
    if revision is not None:
        headers['X-Expected-Revision'] = str(revision)
    response = request(app, 'POST', path, body, headers)
    assert response.status_code in (200, 201), response.text
    return response.json()['data']


def create(app, body, stage):
    identity = post(app, '/api/v1/changes', body)['change_id']
    path = '/api/v1/changes/' + identity
    if stage != 'created':
        post(app, path + '/evaluation-runs', {'suite_version_id': body['suite_version_id'],
             'case_inputs': [{'case_id': case, 'claim_days': 30, 'case_context': {}}
                             for case in ('case-a', 'case-b')]}, revision=1)
    if stage == 'approved':
        post(app, path + '/submit', {}, revision=2)
        post(app, path + '/domain-decision', {'decision': 'APPROVE', 'reason': 'Independent domain review'},
             'reviewer', 3)
        post(app, path + '/release-decision', {'decision': 'APPROVE', 'reason': 'Independent release review'},
             'approver', 4)
    return identity


@pytest.mark.parametrize('stage', ['created', 'evaluated', 'approved'])
def test_evidence_refs_match_stored_hashes_without_payloads(tmp_path, stage):
    app, factory, body = fixture(tmp_path)
    try:
        identity = create(app, body, stage)
        with factory.begin() as db:
            unrelated_adapter = str(uuid4())
            add_payload(db, m.AdapterSnapshot, {'schema': 'adapter_v1', 'tenant_id': 'tenant-a',
                'id': unrelated_adapter, 'kind': 'unrelated-private-adapter', 'credential': 'MUST_NOT_LEAK'})
        response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['historical_integrity'] == 'VALID'
        assert data['external_anchor'] == 'NOT_CONFIGURED'
        refs = data['immutable_refs']
        with factory() as db:
            for name, model, key in (
                ('candidate_snapshot_ref', m.CandidateSnapshot, 'candidate_snapshot_id'),
                ('source_bundle_ref', m.SourceBundle, 'source_bundle_id'),
                ('dataset_ref', m.DatasetSnapshot, 'dataset_version_id'),
                ('suite_ref', m.SuiteSnapshot, 'suite_version_id'),
                ('evaluator_ref', m.EvaluatorSnapshot, 'evaluator_version_id'),
            ):
                row = db.get(model, ('tenant-a', body[key]))
                assert refs[name] == {'id': row.id, 'payload_sha256': row.payload_sha256}
            for name, model in (
                ('run_refs', m.EvaluationRun), ('decision_refs', m.DecisionNote),
                ('transition_refs', m.ChangeTransition),
            ):
                rows = db.execute(select(model).where(model.tenant_id == 'tenant-a', model.change_id == identity)).scalars()
                expected = {row.id: row.payload_sha256 for row in rows}
                assert {ref['id']: ref['payload_sha256'] for ref in refs[name]} == expected
            events = db.execute(select(m.AuditEvent).where(m.AuditEvent.subject_id == identity)).scalars()
            assert {ref['id']: ref['payload_sha256'] for ref in refs['audit_event_refs']} == {row.id: row.payload_sha256 for row in events}
            revisions = db.execute(select(m.ChangeRevision).where(m.ChangeRevision.change_id == identity)).scalars()
            assert refs['change_revision_refs'] == [
                {'change_id': identity, 'revision': row.revision, 'payload_sha256': row.payload_sha256}
                for row in sorted(revisions, key=lambda row: row.revision)]
            for name, model in (('assessment_ref', m.Assessment), ('approval_envelope_ref', m.ApprovalEnvelope)):
                row = db.execute(select(model).where(model.change_id == identity)).scalar_one_or_none()
                assert refs[name] == ({'change_id': identity, 'payload_sha256': row.payload_sha256} if row else None)
            for name, model in (('source_refs', m.SourceSnapshot), ('policy_refs', m.PolicySnapshot),
                                ('source_eligibility_refs', m.SourceEligibilitySnapshot)):
                expected = {row.id: row.payload_sha256 for row in db.execute(select(model)).scalars()}
                assert {ref['id']: ref['payload_sha256'] for ref in refs[name]} == expected
            expected_adapter = db.execute(select(m.AdapterSnapshot).where(m.AdapterSnapshot.id != unrelated_adapter)).scalar_one()
            assert refs['adapter_refs'] == [{'id': expected_adapter.id, 'payload_sha256': expected_adapter.payload_sha256}]
        assert refs['model_ref'] is None and refs['prompt_ref'] is None
        assert unrelated_adapter not in response.text and 'MUST_NOT_LEAK' not in response.text
        assert 'case_inputs' not in response.text and 'case_results' not in response.text
        assert 'canonical_payload' not in response.text and 'claim_days' not in response.text
    finally:
        factory.kw['bind'].dispose()


def test_evidence_refs_are_authorized_and_cross_tenant_hidden(tmp_path):
    app, factory, body = fixture(tmp_path)
    try:
        identity = create(app, body, 'created')
        for actor, status in [('missing', 401), ('no-role', 403), ('outsider', 404)]:
            response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence',
                               headers={'Authorization': 'Bearer ' + actor})
            assert response.status_code == status
            assert 'immutable_refs' not in response.text
            assert body['candidate_snapshot_id'] not in response.text
    finally:
        factory.kw['bind'].dispose()


def test_invalid_evidence_returns_diagnostics_without_verified_refs(tmp_path):
    app, factory, body = fixture(tmp_path)
    try:
        identity = create(app, body, 'approved')
        with factory.begin() as db:
            db.execute(text('DROP TRIGGER v1_change_revision_no_update'))
            db.execute(update(m.ChangeRevision).where(m.ChangeRevision.change_id == identity,
                m.ChangeRevision.revision == 1).values(payload_sha256='f' * 64))
        response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence')
        assert response.status_code == 200
        data = response.json()['data']
        assert data == {'historical_integrity': 'INVALID', 'current_approval_eligibility': 'BLOCKED',
                        'external_anchor': 'NOT_CONFIGURED', 'approved_revision': None,
                        'envelope_sha256': None, 'immutable_refs': None}
    finally:
        factory.kw['bind'].dispose()


def test_missing_canonical_candidate_identity_returns_invalid_diagnostic(tmp_path):
    app, factory, body = fixture(tmp_path)
    try:
        identity = create(app, body, 'created')
        with factory.begin() as db:
            candidate = db.get(m.CandidateSnapshot, ('tenant-a', body['candidate_snapshot_id']))
            payload = json.loads(candidate.canonical_payload)
            del payload['id']
            db.execute(text('DROP TRIGGER v1_candidate_snapshot_no_update'))
            db.execute(update(m.CandidateSnapshot).where(m.CandidateSnapshot.id == candidate.id).values(
                canonical_payload=canonical_bytes(payload), payload_sha256=content_hash('candidate', payload)))
        response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence')
        assert response.status_code == 200
        assert response.json()['data']['historical_integrity'] == 'INVALID'
        assert response.json()['data']['immutable_refs'] is None
    finally:
        factory.kw['bind'].dispose()


def test_legacy_run_returns_unverified_diagnostic_without_refs(tmp_path, monkeypatch):
    from service.evaluation import runner

    app, factory, body = fixture(tmp_path)
    original = runner.prepare_run

    def legacy_run(history, *args, **kwargs):
        run = original(history, *args, **kwargs)
        refs = history['refs']
        adapter = next(adapter for adapter in refs['adapters']
                       if adapter['id'] == refs['candidate_snapshot']['adapter_version_id'])
        run['schema'] = 'evaluation_run_v1'
        run['run_config_sha256'] = content_hash('run-config',
            {name: refs[name] for name in ('candidate_snapshot', 'suite', 'evaluator', 'model', 'prompt')}
            | {'adapter': adapter})
        return run

    try:
        monkeypatch.setattr(runner, 'prepare_run', legacy_run)
        identity = create(app, body, 'evaluated')
        monkeypatch.setattr(runner, 'prepare_run', original)
        response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence')
        assert response.status_code == 200
        assert response.json()['data'] == {
            'historical_integrity': 'LEGACY_UNVERIFIED', 'current_approval_eligibility': 'BLOCKED',
            'external_anchor': 'NOT_CONFIGURED', 'approved_revision': None,
            'envelope_sha256': None, 'immutable_refs': None}
        current = request(app, 'GET', f'/api/v1/changes/{identity}')
        assert current.status_code == 200
        assert current.json()['data']['historical_integrity'] == 'LEGACY_UNVERIFIED'
        assert current.json()['data']['latest_run'] is None
        assert 'snapshot' not in current.json()['data']
    finally:
        factory.kw['bind'].dispose()
