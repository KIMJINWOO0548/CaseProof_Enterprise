"""Execution snapshots are bound before review, with an explicit historical-run boundary."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text, update

from service import models_v1 as m
from service.api.errors import DomainError
from service.api.schemas_v1 import EvaluationRun, EvaluationRunV2
from service.commands import execute_command
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.types import json_payload
from service.evaluation.config import execution_config_sha256
from service.repositories import PURPOSES, add_payload, decode, load_history
from tests.v1.helpers import command, dump, evaluated, setup


@pytest.mark.parametrize('model,body_key', [(m.DatasetSnapshot, 'dataset_version_id'), (m.SourceBundle, 'source_bundle_id')])
def test_rehashed_execution_snapshot_before_review_is_rejected(tmp_path, model, body_key):
    factory, actors, body = setup(tmp_path)
    try:
        identity, recorded = evaluated(factory, actors, body)
        assert recorded.data['run']['gate_summary'] == 'PASS'
        with factory.begin() as db:
            row = db.get(model, ('tenant-a', body[body_key]))
            changed = decode(row)
            changed['description'] = 'Changed after execution, before approval'
            db.execute(text(f'DROP TRIGGER {model.__table__.name}_no_update'))
            db.execute(update(model).where(model.id == row.id).values(
                canonical_payload=canonical_bytes(changed), payload_sha256=content_hash(PURPOSES[model], changed)))
        before = dump(factory)
        with factory() as db, pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
            load_history(db, 'tenant-a', identity)
        with pytest.raises(DomainError, match='EVIDENCE_RECORD_TAMPERED'):
            execute_command(factory, actors['analyst'], command({}, 'submit', identity, 2))
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()


def legacy_evaluated(tmp_path, monkeypatch):
    """Create a coherent historical V1 row and ledger without rewriting stored records."""
    from service.evaluation import runner
    factory, actors, body = setup(tmp_path)
    identity = execute_command(factory, actors['analyst'], command(body)).data['change_id']
    payload = {'suite_version_id': body['suite_version_id'], 'case_inputs': [
        {'case_id': case, 'claim_days': 30, 'case_context': {}} for case in ('case-a', 'case-b')]}
    request = command(payload, 'evaluation-runs', identity, 1, key='historical_v1_evaluation')
    original = runner.prepare_run

    def historical(history, *args):
        run = original(history, *args)
        refs = history['refs']
        run.update(schema='evaluation_run_v1', run_config_sha256=content_hash('run-config',
            {name: refs[name] for name in ('candidate_snapshot', 'suite', 'evaluator', 'model', 'prompt')}
            | {'adapter': refs['adapters'][0]}))
        return EvaluationRun.model_validate(run).model_dump(by_alias=True)

    with monkeypatch.context() as patch:
        patch.setattr(runner, 'prepare_run', historical)
        recorded = execute_command(factory, actors['analyst'], request)
    return factory, actors, identity, request, recorded


def test_legacy_run_remains_immutable_and_cannot_be_verified_or_resealed(tmp_path, monkeypatch):
    factory, actors, identity, original_request, recorded = legacy_evaluated(tmp_path, monkeypatch)
    try:
        before = dump(factory)
        with factory() as db:
            row = db.get(m.EvaluationRun, ('tenant-a', recorded.data['run']['id']))
            assert row.schema_version == 'evaluation_run_v1'
            assert EvaluationRun.model_validate(decode(row)).model_dump(by_alias=True) == decode(row)
            with pytest.raises(DomainError, match='EXECUTION_CONFIG_UNVERIFIED') as rejected:
                load_history(db, 'tenant-a', identity)
            assert rejected.value.status_code == 409
        for request in (command({}, 'submit', identity, 2), command(json_payload(original_request.body), 'evaluation-runs', identity, 2)):
            with pytest.raises(DomainError, match='EXECUTION_CONFIG_UNVERIFIED'):
                execute_command(factory, actors['analyst'], request)
        replay = execute_command(factory, actors['analyst'], original_request)
        assert replay.replayed and replay.status_code == recorded.status_code == 201
        assert replay.data == recorded.data
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()


def test_execution_config_v2_has_frozen_versioned_digest_and_all_snapshot_inputs():
    refs = {name: {'fixture': name} for name in ('candidate_snapshot', 'source_bundle', 'dataset', 'suite', 'evaluator')}
    refs.update(model=None, prompt=None)
    adapter = {'kind': 'fake-deterministic', 'id': 'selected-adapter'}
    expected = '5400353f234101ae2d2ff74d86555bc4af142b65ac42b996f7c69f4c2a64fd48'
    assert execution_config_sha256(refs, adapter) == expected
    for name in refs:
        changed = deepcopy(refs)
        changed[name] = {'fixture': 'changed-' + name}
        assert execution_config_sha256(changed, adapter) != expected
    assert execution_config_sha256(refs, dict(adapter, kind='changed-adapter')) != expected


def test_v2_specimen_matches_new_schema_and_keeps_v1_specimen_unchanged():
    from tests.v1.test_contracts import assert_schema
    from service.api.errors import error_payload
    root = Path(__file__).parents[2] / 'contracts/examples'
    old = json.loads((root / 'run-complete.json').read_text(encoding='utf-8'))
    new = json.loads((root / 'run-v2-complete.json').read_text(encoding='utf-8'))
    assert old['schema'] == 'evaluation_run_v1' and new['schema'] == 'evaluation_run_v2'
    assert EvaluationRun.model_validate(old).model_dump(by_alias=True) == old
    assert EvaluationRunV2.model_validate(new).model_dump(by_alias=True) == new
    assert_schema(new, 'evaluation-run-v2.schema.json')
    assert_schema(error_payload(DomainError('EXECUTION_CONFIG_UNVERIFIED'), str(uuid4())), 'error.schema.json')
    with pytest.raises(ValidationError):
        EvaluationRunV2.model_validate(old)
    with pytest.raises(ValidationError):
        EvaluationRun.model_validate(new)


def test_unrelated_new_dataset_and_source_bundle_preserve_v2_seal(tmp_path):
    from tests.v1.test_evidence import approved
    from service.domain.evidence import verify_evidence
    factory, _, _, history = approved(tmp_path)
    try:
        assert all(run['schema'] == 'evaluation_run_v2' for run in history['runs'])
        with factory.begin() as db:
            for model, name in ((m.DatasetSnapshot, 'dataset'), (m.SourceBundle, 'source_bundle')):
                payload = deepcopy(history['refs'][name])
                payload.update(id=str(uuid4()), description='New unrelated registered version')
                add_payload(db, model, payload)
                if name == 'source_bundle':
                    for member in payload['members']:
                        db.add(m.SourceBundleMember(tenant_id='tenant-a', source_bundle_id=payload['id'],
                            source_id=member['source_id'], policy_id=member['policy_id']))
        with factory() as db:
            loaded = load_history(db, 'tenant-a', history['snapshot']['change_id'])
        assert loaded['assessment'] == history['assessment'] and loaded['envelope'] == history['envelope']
        assert loaded['runs'] == history['runs']
        assert verify_evidence(loaded)['historical_integrity'] == 'VALID'
    finally:
        factory.kw['bind'].dispose()
