"""Detect individual FK/link corruption without rewriting sealed payloads."""
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text, update

from service import models_v1 as m
from service.api.errors import DomainError
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.evidence import verify_evidence
from service.repositories import add_payload, decode, load_history
from tests.v1.helpers import pending_release
from tests.v1.test_evidence import approved


LINKS = (m.AssessmentRunRef, m.AssessmentDecisionRef, m.AssessmentTransitionRef)


@pytest.mark.parametrize('model', LINKS)
@pytest.mark.parametrize('damage', ['delete', 'extra', 'redirect'])
def test_assessment_links_match_manifest(tmp_path, model, damage):
    factory, actors, body, history = approved(tmp_path)
    other_id = pending_release(factory, actors, body)
    try:
        with factory.begin() as db:
            row = db.execute(select(model)).scalars().first()
            table = model.__table__.name
            if damage == 'delete':
                db.execute(text(f'DROP TRIGGER {table}_no_delete'))
                db.execute(delete(model).where(model.id == row.id))
            else:
                target = {m.AssessmentRunRef: m.EvaluationRun, m.AssessmentDecisionRef: m.DecisionNote,
                          m.AssessmentTransitionRef: m.ChangeTransition}[model]
                other = db.execute(select(target).where(target.change_id == other_id)).scalars().first()
                field = {m.AssessmentRunRef: 'run_id', m.AssessmentDecisionRef: 'decision_id',
                         m.AssessmentTransitionRef: 'transition_id'}[model]
                values = {field: other.id}
                if model is m.AssessmentTransitionRef:
                    event = db.execute(select(m.AuditEvent).where(m.AuditEvent.transition_id == other.id)).scalar_one()
                    values['event_id'] = event.id
                if damage == 'redirect':
                    db.execute(text(f'DROP TRIGGER {table}_no_update'))
                    db.execute(update(model).where(model.id == row.id).values(**values))
                else:
                    db.add(model(tenant_id=row.tenant_id, id=str(uuid4()), assessment_id=row.assessment_id, **values))
        with factory() as db, pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
            load_history(db, 'tenant-a', history['snapshot']['change_id'])
    finally:
        factory.kw['bind'].dispose()


@pytest.mark.parametrize('model,field', [
    *[(m.Assessment, name) for name in ('candidate_snapshot_id', 'source_bundle_id', 'dataset_version_id',
        'suite_version_id', 'evaluator_version_id', 'model_id', 'prompt_id', 'source_eligibility_snapshot_id')],
    *[(m.ApprovalEnvelope, name) for name in ('release_decision_id', 'release_transition_id', 'release_event_id')],
    (m.IdempotencyRecord, 'change_id'),
])
def test_nested_fk_projection_matches_untouched_canonical_bytes(tmp_path, model, field):
    factory, _, _, _ = approved(tmp_path)
    try:
        with factory() as db:
            row = db.execute(select(model)).scalars().first()
            sealed = row.canonical_payload
            setattr(row, field, str(uuid4()))
            with pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
                decode(row)
            assert row.canonical_payload == sealed
    finally:
        factory.kw['bind'].dispose()


def test_nested_ref_malformed_is_domain_error(tmp_path):
    factory, _, _, _ = approved(tmp_path)
    try:
        with factory() as db:
            row = db.execute(select(m.Assessment)).scalar_one()
            payload = decode(row)
            payload['candidate_snapshot_ref'] = []
            row.canonical_payload = canonical_bytes(payload)
            row.payload_sha256 = content_hash('assessment', payload)
            with pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
                decode(row)
    finally:
        factory.kw['bind'].dispose()


def test_loaded_approved_history_checks_seal_and_preserves_withdrawal(tmp_path, monkeypatch):
    factory, _, _, history = approved(tmp_path)
    try:
        with factory.begin() as db:
            revoked = dict(history['refs']['source_eligibility'][0], id=str(uuid4()), sequence=2, eligible=False)
            add_payload(db, m.SourceEligibilitySnapshot, revoked)
        with factory() as db:
            loaded = load_history(db, 'tenant-a', history['snapshot']['change_id'])
            assert verify_evidence(loaded)['historical_integrity'] == 'VALID'
            assert verify_evidence(loaded)['current_approval_eligibility'] == 'BLOCKED'
        monkeypatch.setattr('service.domain.evidence.verify_evidence', lambda _: {'historical_integrity': 'INVALID'})
        with factory() as db, pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
            load_history(db, 'tenant-a', history['snapshot']['change_id'])
    finally:
        factory.kw['bind'].dispose()
