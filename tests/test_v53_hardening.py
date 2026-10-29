"""v5.3 regressions against the real API and temporary SQLite databases.

Mutations deliberately simulate partial DB corruption; they do not prove resistance
to a DB administrator rewriting the entire history and its head hash.
"""
import copy
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from reference.evidence_pack import canonical_json, digest
from service.app import create_app
from service.models import AuditEvent, Change, DecisionNote, Evaluation, Tenant, User
from test_service import (
    auth, create, evaluate, fx, good_request, ready_for_domain, ready_for_release,
)


REASON = 'Independent synthetic review completed'


def decision(client, change, stage='release', verdict='APPROVE', **body):
    return client.post(
        f"/api/changes/{change['id']}/{stage}-decision",
        headers=auth('aurora-approver' if stage == 'release' else 'aurora-reviewer'),
        json={'expected_revision': change['revision'], 'decision': verdict,
              'reason': REASON, **body},
    )


def counts(app, cid):
    with app.state.session_factory() as db:
        return tuple(len(db.execute(select(model).where(
            model.change_id == cid)).scalars().all())
            for model in (Evaluation, DecisionNote)) + (
                len(db.execute(select(AuditEvent)).scalars().all()),
                db.get(Change, cid).revision,
                db.get(Change, cid).status,
            )


def evidence(client, cid):
    return client.get(f'/api/changes/{cid}/evidence', headers=auth('aurora-auditor'))


def assert_integrity_failed(client, app, cid):
    # Get an HTTP result even if the vulnerable baseline raises internally.
    with TestClient(app, raise_server_exceptions=False) as guarded:
        response = evidence(guarded, cid)
    assert response.status_code in (200, 409), response.text
    if response.status_code == 200:
        assert response.json()['record_integrity_verified'] is False, response.json()
        assert response.json()['integrity_issues'], response.json()


def rehash_history(db, rows):
    """Keep the hash chain valid so tests isolate semantic history validation."""
    for sequence, row in enumerate(rows, 1):
        row.sequence = -sequence
    db.flush()
    previous = '0' * 64
    for sequence, row in enumerate(rows, 1):
        row.sequence = sequence
        row.prev_hash = previous
        row.event_hash = digest({'sequence': sequence, 'prev_hash': previous,
                                 'event': json.loads(row.event_json)})
        previous = row.event_hash
    tenant = db.get(Tenant, 'AURORA_NONLIFE')
    tenant.audit_seq, tenant.audit_head = len(rows), previous


def history(db):
    return db.execute(select(AuditEvent).where(
        AuditEvent.tenant_id == 'AURORA_NONLIFE').order_by(AuditEvent.sequence)).scalars().all()


def test_status_only_mutation_cannot_skip_domain_review(fx):
    client, app = fx
    change = ready_for_domain(client)
    with app.state.session_factory() as db:
        db.get(Change, change['id']).status = 'PENDING_RELEASE'
        db.commit()
    before = counts(app, change['id'])
    result = decision(client, change)
    assert result.status_code == 409, result.text
    assert result.json()['detail']['code'] == 'EVIDENCE_RECORD_TAMPERED'
    assert counts(app, change['id']) == before
    assert_integrity_failed(client, app, change['id'])


@pytest.mark.parametrize('field,value', [
    ('status', 'DRAFT'), ('status', 'APPROVED_FOR_DEMO'),
    ('revision', 40), ('domain_reviewer_id', None),
    ('domain_reviewer_id', 'aurora-auditor'),
    ('domain_reviewer_id', 'aurora-analyst'),
    ('release_approver_id', 'aurora-approver'),
    ('approved_evidence_hash', 'f' * 64),
])
def test_change_projection_mutations_are_detected(fx, field, value):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        setattr(db.get(Change, change['id']), field, value)
        db.commit()
    assert_integrity_failed(client, app, change['id'])
    before = counts(app, change['id'])
    assert decision(client, change).status_code == 409
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('field,value', [
    ('approved_evidence_hash', None), ('approved_evidence_hash', 'e' * 64),
    ('release_approver_id', None), ('release_approver_id', 'aurora-reviewer'),
    ('domain_reviewer_id', 'aurora-auditor'), ('revision', 99),
    ('status', 'PENDING_RELEASE'),
])
def test_approved_projection_and_hash_are_bound_to_audit(fx, field, value):
    client, app = fx
    change = ready_for_release(client)
    assert decision(client, change).status_code == 200
    with app.state.session_factory() as db:
        setattr(db.get(Change, change['id']), field, value)
        db.commit()
    assert_integrity_failed(client, app, change['id'])


@pytest.mark.parametrize('mutation', [
    'missing_genesis', 'missing_submit', 'duplicate_submit',
    'swap_genesis_and_evaluation', 'swap_submit_and_domain',
    'evaluate_after_submit', 'revision_gap', 'revision_bool', 'revision_string',
    'unknown_kind', 'domain_actor_is_requester', 'audit_actor_column',
    'duplicate_domain_note_and_event', 'submit_actor_is_reviewer',
    'evaluation_actor_is_reviewer', 'genesis_actor_is_reviewer',
    'one_evaluation_before_submit',
])
def test_semantic_history_corruption_is_rejected_even_with_valid_hashes(fx, mutation):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        rows = history(db)
        if mutation in ('missing_genesis', 'missing_submit'):
            removed = rows.pop(0 if mutation == 'missing_genesis' else 3)
            db.delete(removed)
        elif mutation == 'duplicate_submit':
            original = rows[3]
            duplicate = AuditEvent(id=str(uuid4()), tenant_id=original.tenant_id,
                actor_id=original.actor_id, sequence=90, prev_hash='0' * 64,
                event_json=original.event_json, event_hash='0' * 64)
            db.add(duplicate)
            rows.insert(4, duplicate)
        elif mutation == 'swap_genesis_and_evaluation':
            rows[0], rows[1] = rows[1], rows[0]
        elif mutation == 'swap_submit_and_domain':
            rows[3], rows[4] = rows[4], rows[3]
        elif mutation == 'evaluate_after_submit':
            rows[2], rows[3] = rows[3], rows[2]
        elif mutation.startswith('revision_'):
            event = json.loads(rows[1].event_json)
            event['details']['revision_from'] = {
                'revision_gap': 9, 'revision_bool': True, 'revision_string': '1',
            }[mutation]
            rows[1].event_json = canonical_json(event).decode()
        elif mutation == 'unknown_kind':
            event = json.loads(rows[3].event_json)
            event['kind'] = 'UNRECOGNIZED_TRANSITION'
            rows[3].event_json = canonical_json(event).decode()
        elif mutation == 'domain_actor_is_requester':
            event = json.loads(rows[4].event_json)
            event['actor_id'] = rows[4].actor_id = 'aurora-analyst'
            rows[4].event_json = canonical_json(event).decode()
            note = db.execute(select(DecisionNote).where(
                DecisionNote.change_id == change['id'])).scalar_one()
            note.actor_id = 'aurora-analyst'
            db.get(Change, change['id']).domain_reviewer_id = 'aurora-analyst'
        elif mutation == 'audit_actor_column':
            rows[1].actor_id = 'aurora-auditor'
        elif mutation in ('submit_actor_is_reviewer', 'evaluation_actor_is_reviewer',
                          'genesis_actor_is_reviewer'):
            index = {'submit_actor_is_reviewer': 3, 'evaluation_actor_is_reviewer': 1,
                     'genesis_actor_is_reviewer': 0}[mutation]
            event = json.loads(rows[index].event_json)
            event['actor_id'] = rows[index].actor_id = 'aurora-reviewer'
            rows[index].event_json = canonical_json(event).decode()
            if mutation == 'evaluation_actor_is_reviewer':
                db.get(Evaluation, event['details']['evaluation_id']).actor_id = 'aurora-reviewer'
        elif mutation == 'one_evaluation_before_submit':
            removed = rows.pop(2)
            db.delete(db.get(Evaluation, json.loads(removed.event_json)['details']['evaluation_id']))
            db.delete(removed)
            db.get(Change, change['id']).revision -= 1
        elif mutation == 'duplicate_domain_note_and_event':
            original = db.execute(select(DecisionNote).where(
                DecisionNote.change_id == change['id'])).scalar_one()
            note = DecisionNote(id=str(uuid4()), tenant_id=original.tenant_id,
                change_id=original.change_id, actor_id=original.actor_id,
                stage=original.stage, decision=original.decision,
                reason=original.reason, created_at=original.created_at)
            db.add(note)
            event = json.loads(rows[-1].event_json)
            event['details']['decision_id'] = note.id
            duplicate = AuditEvent(id=str(uuid4()), tenant_id=original.tenant_id,
                actor_id=original.actor_id, sequence=90, prev_hash='0' * 64,
                event_json=canonical_json(event).decode(), event_hash='0' * 64)
            db.add(duplicate)
            rows.append(duplicate)
        if mutation in ('missing_genesis','missing_submit','one_evaluation_before_submit'):
            # The retained transition ledger adds FKs absent from the source v5.3 demo.
            with pytest.raises(IntegrityError):
                rehash_history(db, rows)
            db.rollback()
            assert evidence(client, change['id']).json()['record_integrity_verified'] is True
            return
        rehash_history(db, rows)
        db.commit()
    assert_integrity_failed(client, app, change['id'])
    before = counts(app, change['id'])
    assert decision(client, change).status_code == 409
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('mutation', ['release_actor_is_reviewer', 'approval_hash'])
def test_approved_history_enforces_separation_and_manifest_hash(fx, mutation):
    client, app = fx
    change = ready_for_release(client)
    assert decision(client, change).status_code == 200
    with app.state.session_factory() as db:
        rows = history(db)
        event = json.loads(rows[-1].event_json)
        if mutation == 'release_actor_is_reviewer':
            event['actor_id'] = rows[-1].actor_id = 'aurora-reviewer'
            note = db.execute(select(DecisionNote).where(
                DecisionNote.change_id == change['id'], DecisionNote.stage == 'RELEASE')).scalar_one()
            note.actor_id = 'aurora-reviewer'
            db.get(Change, change['id']).release_approver_id = 'aurora-reviewer'
        else:
            event['details']['evidence_sha256'] = 'b' * 64
            db.get(Change, change['id']).approved_evidence_hash = 'b' * 64
        rows[-1].event_json = canonical_json(event).decode()
        rehash_history(db, rows)
        db.commit()
    assert_integrity_failed(client, app, change['id'])


@pytest.mark.parametrize('mutation', ['delete_note', 'duplicate_note', 'change_note_id',
                                     'delete_evaluation', 'change_evaluation_id'])
def test_record_counts_and_ids_cannot_diverge_from_audit(fx, mutation):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        if 'note' in mutation:
            row = db.execute(select(DecisionNote).where(
                DecisionNote.change_id == change['id'])).scalar_one()
        else:
            row = db.execute(select(Evaluation).where(
                Evaluation.change_id == change['id'])).scalars().first()
        if mutation.startswith('delete'):
            db.delete(row)
        elif mutation == 'duplicate_note':
            db.add(DecisionNote(id=str(uuid4()), tenant_id=row.tenant_id,
                change_id=row.change_id, actor_id=row.actor_id, stage=row.stage,
                decision=row.decision, reason=row.reason, created_at=row.created_at))
        else:
            row.id = str(uuid4())
        if mutation in ('delete_note','change_note_id'):
            # Bound decisions cannot be removed or reidentified under the retained ledger FK.
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            assert evidence(client, change['id']).json()['record_integrity_verified'] is True
            return
        db.commit()
    assert_integrity_failed(client, app, change['id'])
    before = counts(app, change['id'])
    assert decision(client, change).status_code == 409
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('malformed', [None, [], 'wrong type', {'subject_id': 'placeholder'},
                                     {'details': []}])
def test_malformed_audit_objects_fail_closed_without_500(fx, malformed):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        rows = history(db)
        value = copy.deepcopy(malformed)
        if isinstance(value, dict):
            value['subject_id'] = change['id']
        rows[0].event_json = json.dumps(value)
        rehash_history(db, rows)
        db.commit()
    assert_integrity_failed(client, app, change['id'])
    assert decision(client, change).status_code == 409


@pytest.mark.parametrize('field,malformed', [
    ('request_json', 'null'), ('request_json', '[]'),
    ('result_json', '{invalid'), ('result_json', 'null'), ('result_json', '[]'),
])
def test_malformed_evaluation_objects_fail_closed_without_500(fx, field, malformed):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        row = db.execute(select(Evaluation).where(
            Evaluation.change_id == change['id'])).scalars().first()
        setattr(row, field, malformed)
        db.commit()
    assert_integrity_failed(client, app, change['id'])
    assert decision(client, change).status_code == 409


@pytest.mark.parametrize('replay', [False, True])
def test_only_requester_can_evaluate_or_replay(fx, replay):
    client, app = fx
    change = create(client)
    key = 'requester-only-key-12345'
    if replay:
        assert evaluate(client, change, key=key).status_code == 201
    with app.state.session_factory() as db:
        db.get(User, 'aurora-reviewer').roles_json = '["DOMAIN_REVIEWER","ANALYST"]'
        db.commit()
    before = counts(app, change['id'])
    response = evaluate(client, change, who='aurora-reviewer', key=key)
    assert response.status_code == 403, response.text
    assert response.json()['detail']['code'] == 'REQUESTER_ONLY'
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('replay', [False, True])
@pytest.mark.parametrize('mutation', ['revision', 'evaluation', 'audit'])
def test_new_evaluation_checks_integrity_and_replay_preserves_committed_result(fx, replay, mutation):
    client, app = fx
    change = create(client)
    key = 'integrity-replay-key-12345'
    first = evaluate(client, change, key=key)
    assert first.status_code == 201
    with app.state.session_factory() as db:
        row = db.get(Change, change['id'])
        if mutation == 'revision':
            row.revision = 50
        elif mutation == 'evaluation':
            item = db.execute(select(Evaluation).where(
                Evaluation.change_id == change['id'])).scalar_one()
            item.result_json = '{"verdict":"PASS","expected_days":999}'
        else:
            history(db)[0].event_json = '{"tampered":true}'
        change['revision'] = row.revision
        db.commit()
    before = counts(app, change['id'])
    response = evaluate(client, change, key=key if replay else 'fresh-evaluation-key-12345',
                        revision=1 if replay else change['revision'])
    if replay:
        # Retained all-write idempotency replays the original fingerprint/result before
        # current integrity checks; it does not certify the current evidence (§08.9).
        assert response.status_code == first.status_code
        assert response.json() == {**first.json(), 'replayed': True, 'reused': True}
    else:
        assert response.status_code == 409, response.text
        assert response.json()['detail']['code'] in ('EVIDENCE_RECORD_TAMPERED', 'AUDIT_INTEGRITY_FAILURE')
    assert_integrity_failed(client, app, change['id'])
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('claim_days', [True, False, 30.0, '30', -1, 10000])
def test_claim_days_accepts_only_bounded_json_integers(fx, claim_days):
    client, app = fx
    change = create(client)
    before = counts(app, change['id'])
    response = evaluate(client, change, claim_days=claim_days)
    assert response.status_code == 422, response.text
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('claim_days', [0, 9999])
def test_claim_days_integer_boundaries_remain_valid_requests(fx, claim_days):
    client, _ = fx
    response = evaluate(client, create(client), claim_days=claim_days)
    assert response.status_code == 201, response.text


@pytest.mark.parametrize('revision', [True, 4.0, '4', 0, -1])
def test_expected_revision_body_is_a_strict_positive_integer(fx, revision):
    client, app = fx
    change = ready_for_domain(client)
    before = counts(app, change['id'])
    response = decision(client, change, 'domain', expected_revision=revision)
    assert response.status_code == 422, response.text
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('revision', ['1.0', '+1', '01', ' 1', '1 ', '0', '-1', 'true'])
def test_expected_revision_header_rejects_noncanonical_or_nonpositive_values(fx, revision):
    client, app = fx
    change = create(client)
    before = counts(app, change['id'])
    response = evaluate(client, change, revision=revision)
    assert response.status_code == 422, response.text
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('stage', ['domain', 'release'])
@pytest.mark.parametrize('reason', [None, '', '       ', 'short', ' 1234567 ', 'x' * 501,
                                    ' ' * 494 + '12345678'])
def test_decision_reason_requires_eight_to_five_hundred_before_and_after_strip(fx, stage, reason):
    client, app = fx
    change = ready_for_domain(client) if stage == 'domain' else ready_for_release(client)
    before = counts(app, change['id'])
    response = decision(client, change, stage, reason=reason)
    assert response.status_code == 422, response.text
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('reason', ['12345678', 'x' * 500, ' 12345678 ', '가나다라마바사아'])
def test_decision_reason_boundaries_and_strip_are_preserved(fx, reason):
    client, _ = fx
    change = ready_for_domain(client)
    assert decision(client, change, 'domain', reason=reason).status_code == 200
    data = client.get(f"/api/changes/{change['id']}", headers=auth('aurora-analyst')).json()
    assert data['decisions'][0]['reason'] == reason.strip()


@pytest.mark.parametrize('endpoint', ['create', 'evaluate', 'submit', 'domain', 'release'])
def test_unknown_body_fields_are_rejected(fx, endpoint):
    client, app = fx
    if endpoint == 'create':
        response = client.post('/api/changes', headers=auth('aurora-analyst'),
                               json={**good_request(client), 'tenant_id': 'HORIZON_LIFE'})
        assert response.status_code == 422, response.text
        assert client.get('/api/changes', headers=auth('aurora-analyst')).json() == []
        return
    change = (ready_for_release(client) if endpoint == 'release' else
              ready_for_domain(client) if endpoint == 'domain' else create(client))
    before = counts(app, change['id'])
    if endpoint == 'evaluate':
        response = client.post(f"/api/changes/{change['id']}/evaluations",
            headers={**auth('aurora-analyst'), 'Idempotency-Key': 'unknown-field-key-12345',
                     'X-Expected-Revision': str(change['revision'])},
            json={'claim_days': 30, 'basis_date': '2026-06-30', 'rider_codes': [],
                  'as_of_recorded': '2026-10-28T00:00:00+09:00', 'role': 'ADMIN'})
    elif endpoint == 'submit':
        response = client.post(f"/api/changes/{change['id']}/submit",
            headers=auth('aurora-analyst'),
            json={'expected_revision': change['revision'], 'requester_id': 'aurora-reviewer'})
    else:
        response = decision(client, change, endpoint, role='ADMIN')
    assert response.status_code == 422, response.text
    assert counts(app, change['id']) == before


def test_openapi_describes_reason_strict_numbers_and_closed_bodies(fx):
    client, _ = fx
    document = client.get('/openapi.json').json()
    schemas = document['components']['schemas']
    reason = schemas['Decision']['properties']['reason']
    assert 'reason' in schemas['Decision']['required']
    assert reason['minLength'] == 8 and reason['maxLength'] == 500
    assert 'strip' in reason['description']
    for name in ('ChangeCreate', 'EvalRequest', 'Transition', 'Decision'):
        assert schemas[name]['additionalProperties'] is False
    claim = schemas['EvalRequest']['properties']['claim_days']
    assert (claim['type'], claim['minimum'], claim['maximum']) == ('integer', 0, 9999)
    assert claim['x-strict-json-integer'] is True
    assert schemas['Transition']['properties']['expected_revision']['x-strict-json-integer'] is True
    params = document['paths']['/api/changes/{cid}/evaluations']['post']['parameters']
    headers = {item['name']: item for item in params if item['in'] == 'header'}
    assert headers['X-Expected-Revision']['required'] is True
    assert headers['Idempotency-Key']['required'] is True
    assert headers['X-Expected-Revision']['schema']['minimum'] == 1


@pytest.mark.parametrize('url', ['', 'sqlite:///:memory:', 'postgresql://unused.invalid/example'])
def test_non_demo_startup_is_disabled_before_database_connection(url, monkeypatch):
    monkeypatch.delenv('CASEPROOF_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError):
        create_app(url, demo_mode=False)


def test_happy_path_and_replay_preserve_audited_revision_counts(fx):
    client, app = fx
    change = create(client)
    key = 'happy-path-original-key-12345'
    first = evaluate(client, change, key=key)
    assert first.status_code == 201
    replay = evaluate(client, change, key=key)
    assert replay.json()['reused'] is True and replay.json()['id'] == first.json()['id']
    assert counts(app, change['id']) == (1, 0, 2, 2, 'DRAFT')
    change['revision'] = 2
    assert evaluate(client, change, claim_days=20, basis_date='2026-07-01').status_code == 201
    response = client.post(f"/api/changes/{change['id']}/submit", headers=auth('aurora-analyst'),
                           json={'expected_revision': 3})
    assert response.status_code == 200
    domain = decision(client, response.json(), 'domain')
    assert domain.status_code == 200
    released = decision(client, domain.json())
    assert released.status_code == 200
    assert counts(app, change['id']) == (2, 2, 6, 6, 'APPROVED_FOR_DEMO')
    proof = evidence(client, change['id']).json()
    assert proof['record_integrity_verified'] is True
    assert proof['matches_approval'] is True
    assert proof['audit_chain_verified'] is True
    assert proof['external_trust_anchor'] is False
    # A valid historical evaluation retry retains the established API semantics.
    replay = evaluate(client, change, key=key, revision=1)
    assert replay.status_code == 201 and replay.json()['reused'] is True
    # The retained committed-response contract returns the original result revision.
    assert replay.json()['revision'] == first.json()['revision'] == 2
    assert counts(app, change['id']) == (2, 2, 6, 6, 'APPROVED_FOR_DEMO')


@pytest.mark.parametrize('stage', ['domain', 'release'])
def test_rejected_history_is_valid_and_terminal(fx, stage):
    client, app = fx
    change = ready_for_domain(client) if stage == 'domain' else ready_for_release(client)
    response = decision(client, change, stage, 'REJECT')
    assert response.status_code == 200 and response.json()['status'] == 'REJECTED'
    proof = evidence(client, change['id']).json()
    assert proof['record_integrity_verified'] is True and proof['matches_approval'] is None
    before = counts(app, change['id'])
    assert decision(client, response.json(), stage).status_code == 409
    assert counts(app, change['id']) == before


@pytest.mark.parametrize('operation', ['evaluate', 'domain', 'release'])
def test_audit_insert_failure_rolls_back_state_and_related_records(fx, operation):
    client, app = fx
    change = (create(client) if operation == 'evaluate' else
              ready_for_domain(client) if operation == 'domain' else ready_for_release(client))
    before = counts(app, change['id'])
    with app.state.db_engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER reject_audit_insert BEFORE INSERT ON audit_events "
                                "BEGIN SELECT RAISE(ABORT, 'injected audit insert failure'); END"))
    with TestClient(app, raise_server_exceptions=False) as guarded:
        response = (evaluate(guarded, change) if operation == 'evaluate' else
                    decision(guarded, change, operation))
    assert response.status_code == 500
    assert counts(app, change['id']) == before
    assert evidence(client, change['id']).json()['record_integrity_verified'] is True
