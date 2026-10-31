"""Rehashed partial rewrites must still fail the stored approval's cross-record bindings."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from service import models_v1 as m
from service.api.errors import DomainError
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.evidence import verify_evidence
from service.repositories import PURPOSES, add_payload, decode, load_history
from tests.v1.helpers import dump
from tests.v1.test_evidence import approved


@pytest.mark.parametrize('model,field,value', [
    (m.ChangeRevision, 'title', 'Rewritten request title'),
    (m.ChangeTransition, 'occurred_at', '2027-01-01T00:00:00.000000Z'),
    (m.AuditEvent, 'occurred_at', '2027-01-01T00:00:00.000000Z'),
    (m.AuditEvent, 'sequence', 1000),
    (m.EvaluationRun, 'created_at', '2027-01-01T00:00:00.000000Z'),
    (m.DecisionNote, 'reason', 'Rewritten review justification'),
    (m.Assessment, 'tenant_audit_checkpoint', {'sequence': 4, 'head_sha256': 'f' * 64}),
    (m.ApprovalEnvelope, 'approved_at', '2027-01-01T00:00:00.000000Z'),
    (m.CandidateSnapshot, 'description', 'Rewritten candidate configuration'),
    (m.SourceBundle, 'description', 'Rewritten source bundle'),
    (m.SourceSnapshot, 'claim_days', 31),
    (m.PolicySnapshot, 'description', 'Rewritten policy configuration'),
    (m.DatasetSnapshot, 'description', 'Rewritten dataset configuration'),
    (m.SuiteSnapshot, 'required_coverage_labels', ['unobserved-label']),
    (m.EvaluatorSnapshot, 'description', 'Rewritten evaluator configuration'),
    (m.AdapterSnapshot, 'kind', 'rewritten-adapter'),
    (m.AdapterSnapshot, 'description', 'Rewritten adapter configuration'),
    (m.SourceEligibilitySnapshot, 'eligible', False),
], ids=lambda value: value.__name__ if isinstance(value, type) else str(value))
def test_rehashed_record_edit_is_rejected_by_storage_or_history(tmp_path, model, field, value):
    factory, _, _, history = approved(tmp_path)
    try:
        original = dump(factory)
        try:
            with factory.begin() as db:
                row = db.scalars(select(model).order_by(*model.__table__.primary_key.columns)).first()
                changed = decode(row)
                changed[field] = value
                values = {'canonical_payload': canonical_bytes(changed),
                          'payload_sha256': content_hash(PURPOSES[model], changed)}
                if field in model.__table__.columns:
                    values[field] = value
                # Simulate a partial DB-owner rewrite; runtime UPDATE grants remain unchanged.
                db.execute(text(f'DROP TRIGGER {model.__table__.name}_no_update'))
                db.execute(update(model).where(*(column == getattr(row, column.name)
                    for column in model.__table__.primary_key.columns)).values(**values))
        except IntegrityError as blocked:
            assert 'FOREIGN KEY constraint failed' in str(blocked)
            assert dump(factory) == original
            with factory() as db:
                assert verify_evidence(load_history(db, 'tenant-a', history['snapshot']['change_id']))['historical_integrity'] == 'VALID'
            return
        before = dump(factory)
        with factory() as db, pytest.raises(DomainError) as rejected:
            load_history(db, 'tenant-a', history['snapshot']['change_id'])
        assert rejected.value.status_code == 409
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()


@pytest.mark.parametrize('model,field,value', [
    (m.ChangeRevision, 'revision', 6),
    (m.EvaluationRun, 'recorded_revision', 3),
])
def test_unreferenced_extra_record_cannot_join_approved_history(tmp_path, model, field, value):
    factory, _, _, history = approved(tmp_path)
    try:
        with factory.begin() as db:
            extra = decode(db.scalars(select(model).order_by(*model.__table__.primary_key.columns)).first())
            extra[field] = value
            if 'id' in model.__table__.columns:
                extra['id'] = str(uuid4())
            add_payload(db, model, extra)
        before = dump(factory)
        with factory() as db, pytest.raises(DomainError):
            load_history(db, 'tenant-a', history['snapshot']['change_id'])
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()


def test_new_unreferenced_source_version_preserves_frozen_approval(tmp_path):
    factory, _, _, history = approved(tmp_path)
    try:
        original_envelope = deepcopy(history['envelope'])
        original_manifest = deepcopy(history['assessment'])
        with factory.begin() as db:
            source = deepcopy(history['refs']['sources'][0])
            source.update(id=str(uuid4()), policy_version_id='policy-v3', claim_days=31)
            add_payload(db, m.SourceSnapshot, source)
        with factory() as db:
            loaded = load_history(db, 'tenant-a', history['snapshot']['change_id'])
            assert db.get(m.SourceSnapshot, ('tenant-a', source['id'])) is not None
        assert loaded['envelope'] == original_envelope and loaded['assessment'] == original_manifest
        assert source['id'] not in {row['id'] for row in loaded['refs']['sources']}
        assert verify_evidence(loaded)['historical_integrity'] == 'VALID'
    finally:
        factory.kw['bind'].dispose()
