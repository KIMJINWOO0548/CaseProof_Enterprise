"""G1 regression tests against real HTTP handlers and temporary SQLite."""
import json
import pytest
from sqlalchemy import select, func
from test_service import fx, auth, create, evaluate, ready_for_domain, ready_for_release
from service.models import Change, DecisionNote, AuditEvent, Evaluation, User
from service.models import ChangeTransition, Tenant
from sqlalchemy.exc import IntegrityError
import importlib


def decide(client, c, stage='release', who='aurora-approver'):
    return client.post(f"/api/changes/{c['id']}/{stage}-decision", headers=auth(who),
                       json={'expected_revision': c['revision'], 'decision': 'APPROVE',
                             'reason': 'Synthetic review completed'})


def test_status_only_tamper_cannot_create_release_decision(fx):
    client, app = fx
    c = ready_for_domain(client)
    with app.state.session_factory() as db:
        db.get(Change, c['id']).status = 'PENDING_RELEASE'
        db.commit()
        before = db.scalar(select(func.count()).select_from(AuditEvent))
    response = decide(client, c)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'EVIDENCE_RECORD_TAMPERED'
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DecisionNote)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == before


def test_evaluation_is_requester_only_even_with_analyst_role(fx):
    client, app = fx
    c = create(client)
    with app.state.session_factory() as db:
        db.get(User, 'aurora-reviewer').roles_json = json.dumps(['ANALYST', 'DOMAIN_REVIEWER'])
        db.commit()
    response = evaluate(client, c, who='aurora-reviewer')
    assert response.status_code == 403, response.text
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Evaluation)) == 0


def test_manifest_freezes_preapproval_revision_and_domain_evidence(fx):
    client, _ = fx
    c = ready_for_release(client)
    before = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-analyst')).json()
    assert before['content']['pre_approval_revision'] == c['revision']
    assert len(before['content']['domain_decisions']) == 1
    assert decide(client, c).status_code == 200
    after = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-analyst')).json()
    assert after['manifest_sha256'] == before['manifest_sha256']
    assert after['matches_approval'] is True
    assert after['approval_envelope']['assessment_sha256'] == before['manifest_sha256']


@pytest.mark.parametrize('field,value', [('status', 'PENDING_DOMAIN_REVIEW'),
    ('revision', 30), ('domain_reviewer_id', 'aurora-auditor')])
def test_projection_tamper_detected(fx, field, value):
    client, app = fx
    c = ready_for_release(client)
    with app.state.session_factory() as db:
        setattr(db.get(Change, c['id']), field, value)
        db.commit()
    assert decide(client, c).status_code == 409
    evidence = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-auditor')).json()
    assert evidence['record_integrity_verified'] is False


@pytest.mark.parametrize('mutation', ['missing', 'actor', 'order'])
def test_transition_tamper_blocks_approval(fx, mutation):
    client, app = fx
    c = ready_for_release(client)
    with app.state.session_factory() as db:
        rows = db.scalars(select(ChangeTransition).order_by(ChangeTransition.revision_to)).all()
        if mutation == 'missing':
            db.delete(rows[1])
        elif mutation == 'actor':
            rows[-1].actor_id = 'aurora-auditor'
        else:
            rows[1].audit_event_id, rows[2].audit_event_id = rows[2].audit_event_id, rows[1].audit_event_id
        if mutation == 'order':
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            return
        db.commit()
    assert decide(client, c).status_code == 409


def test_domain_note_duplicate_rejected(fx):
    client, app = fx
    c = ready_for_release(client)
    with app.state.session_factory() as db:
        n = db.scalar(select(DecisionNote))
        db.add(DecisionNote(id='duplicate',tenant_id=n.tenant_id,change_id=n.change_id,
            actor_id=n.actor_id,stage=n.stage,decision=n.decision,reason=n.reason,created_at=n.created_at))
        db.commit()
    assert decide(client, c).status_code == 409


@pytest.mark.parametrize('target', ['decision', 'event'])
def test_bound_record_deletion_is_rejected_by_fk(fx, target):
    client, app = fx
    ready_for_release(client)
    with app.state.session_factory() as db:
        model = DecisionNote if target == 'decision' else AuditEvent
        db.delete(db.scalars(select(model)).first())
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_genesis_and_every_revision_have_bound_transitions(fx):
    client, app = fx
    c = ready_for_release(client)
    assert decide(client, c).status_code == 200
    with app.state.session_factory() as db:
        rows = db.scalars(select(ChangeTransition).order_by(ChangeTransition.revision_to)).all()
        assert [t.revision_to for t in rows] == list(range(1, 7))
        assert [t.kind for t in rows] == ['CHANGE_CREATED', 'EVALUATION_RECORDED',
            'EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW', 'DOMAIN_APPROVE', 'APPROVED_FOR_DEMO']
        assert rows[0].from_state == 'NONE' and rows[0].revision_from == 0
        assert len({t.audit_event_id for t in rows}) == 6


@pytest.mark.parametrize('mutation', ['gap', 'duplicate', 'tenant', 'edge'])
def test_transition_constraints(fx, mutation):
    client, app = fx
    create(client)
    with app.state.session_factory() as db:
        t = db.scalar(select(ChangeTransition))
        if mutation == 'gap':
            t.revision_to = 9
        elif mutation == 'tenant':
            t.tenant_id = 'HORIZON_LIFE'
        elif mutation == 'edge':
            t.to_state = 'APPROVED_FOR_DEMO'
        else:
            fields = {col.name: getattr(t, col.name) for col in ChangeTransition.__table__.columns}
            fields['id'] = 'duplicate'
            db.add(ChangeTransition(**fields))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def database_snapshot(app):
    with app.state.session_factory() as db:
        return {model.__tablename__: sorted([tuple(getattr(r,col.name) for col in model.__table__.columns)
            for r in db.scalars(select(model))], key=repr)
            for model in (Change, Evaluation, DecisionNote, AuditEvent, ChangeTransition, Tenant)}


@pytest.mark.parametrize('operation', ['create','evaluate','submit','domain','release','domain_reject','release_reject'])
def test_failure_after_audit_rolls_back_entire_mutation(fx, monkeypatch, operation):
    client, app = fx
    if operation in ('release', 'release_reject'):
        c = ready_for_release(client)
    elif operation in ('domain', 'domain_reject'):
        c = ready_for_domain(client)
    elif operation == 'submit':
        c = create(client)
        c['revision'] = evaluate(client, c).json()['revision']
        c['revision'] = evaluate(client, c, claim_days=20, basis_date='2026-07-01').json()['revision']
    elif operation == 'evaluate':
        c = create(client)
    before = database_snapshot(app)
    module = importlib.import_module('service.app')
    original = module.append_audit
    def fail_after_append(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('injected transaction failure')
    monkeypatch.setattr(module, 'append_audit', fail_after_append)
    with pytest.raises(RuntimeError, match='injected transaction failure'):
        if operation == 'create':
            create(client)
        elif operation == 'evaluate':
            evaluate(client, c)
        elif operation == 'submit':
            client.post(f"/api/changes/{c['id']}/submit", headers=auth('aurora-analyst'),
                        json={'expected_revision':c['revision']})
        else:
            stage = operation.split('_')[0]
            who = 'aurora-reviewer' if stage == 'domain' else 'aurora-approver'
            client.post(f"/api/changes/{c['id']}/{stage}-decision", headers=auth(who),
                json={'expected_revision':c['revision'], 'decision':'REJECT' if 'reject' in operation else 'APPROVE',
                      'reason':'Synthetic decision for rollback'})
    assert database_snapshot(app) == before


def test_legacy_change_is_not_silently_given_genesis(fx):
    client, app = fx
    c = create(client)
    with app.state.session_factory() as db:
        db.delete(db.scalar(select(ChangeTransition)))
        db.commit()
    assert evaluate(client, c).status_code == 409
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ChangeTransition)) == 0


@pytest.mark.parametrize('field,value', [('approval_envelope_hash','0'*64),
    ('assessment_revision',1), ('approved_evidence_hash','0'*64)])
def test_approval_snapshot_tamper_detected(fx, field, value):
    client, app = fx
    c = ready_for_release(client)
    assert decide(client, c).status_code == 200
    with app.state.session_factory() as db:
        setattr(db.get(Change,c['id']),field,value)
        db.commit()
    evidence = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-auditor')).json()
    assert evidence['record_integrity_verified'] is False


def test_malformed_approval_envelope_returns_failed_integrity(fx):
    client, app = fx
    c = ready_for_release(client)
    assert decide(client, c).status_code == 200
    with app.state.session_factory() as db:
        db.get(Change, c['id']).approval_envelope_json = '{'
        db.commit()
    response = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-auditor'))
    assert response.status_code == 200, response.text
    evidence = response.json()
    assert evidence['approval_envelope'] is None
    assert evidence['record_integrity_verified'] is False
    assert evidence['matches_approval'] is False
    assert 'TRANSITION_RECORD_INVALID' in evidence['integrity_issues']


def test_valid_but_changed_envelope_cannot_match_approval(fx):
    client, app = fx
    c = ready_for_release(client)
    assert decide(client, c).status_code == 200
    with app.state.session_factory() as db:
        db.get(Change, c['id']).approval_envelope_json = '{}'
        db.commit()
    evidence = client.get(f"/api/changes/{c['id']}/evidence", headers=auth('aurora-auditor')).json()
    assert evidence['record_integrity_verified'] is False
    assert evidence['matches_approval'] is False
