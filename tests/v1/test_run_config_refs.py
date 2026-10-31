"""Selected synthetic model/prompt bytes are frozen; unrelated registrations are isolated."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import text, update

from service import models_v1 as m
from service.api.errors import DomainError
from service.commands import execute_command
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.evidence import verify_evidence
from service.repositories import PURPOSES, add_payload, decode, load_history
from tests.v1.helpers import command, dump, pending_release, setup


def approved_with_model_and_prompt(tmp_path):
    factory, actors, body = setup(tmp_path)
    with factory.begin() as db:
        model = {'schema': 'model_v1', 'tenant_id': 'tenant-a', 'id': str(uuid4()),
                 'name': 'synthetic-model-v1'}
        prompt = {'schema': 'prompt_v1', 'tenant_id': 'tenant-a', 'id': str(uuid4()),
                  'text': 'Synthetic numeric fixture only; no provider is called.'}
        add_payload(db, m.ModelSnapshot, model)
        add_payload(db, m.PromptSnapshot, prompt)
        candidate = decode(db.get(m.CandidateSnapshot, ('tenant-a', body['candidate_snapshot_id'])))
        candidate.update(id=str(uuid4()), model_id=model['id'], prompt_id=prompt['id'])
        add_payload(db, m.CandidateSnapshot, candidate)
    body = dict(body, candidate_snapshot_id=candidate['id'])
    identity = pending_release(factory, actors, body)
    execute_command(factory, actors['approver'], command(
        {'decision': 'APPROVE', 'reason': 'Independent synthetic review'}, 'release-decision', identity, 4))
    with factory() as db:
        history = load_history(db, 'tenant-a', identity)
        for cls, name in ((m.ModelSnapshot, 'model'), (m.PromptSnapshot, 'prompt')):
            payload = history['refs'][name]
            row = db.get(cls, ('tenant-a', payload['id']))
            assert row.canonical_payload == canonical_bytes(payload)
            assert history['assessment'][name + '_ref'] == {
                'id': row.id, 'payload_sha256': row.payload_sha256}
            assert row.payload_sha256 == content_hash(PURPOSES[cls], payload)
    assert verify_evidence(history)['historical_integrity'] == 'VALID'
    return factory, history


@pytest.mark.parametrize('model,name', [(m.ModelSnapshot, 'model'), (m.PromptSnapshot, 'prompt')])
def test_rehashed_selected_model_or_prompt_invalidates_approval(tmp_path, model, name):
    factory, history = approved_with_model_and_prompt(tmp_path)
    try:
        with factory.begin() as db:
            changed = deepcopy(history['refs'][name])
            changed['description'] = 'Rewritten selected configuration'
            db.execute(text(f'DROP TRIGGER {model.__table__.name}_no_update'))
            db.execute(update(model).where(model.id == changed['id']).values(
                canonical_payload=canonical_bytes(changed), payload_sha256=content_hash(name, changed)))
        before = dump(factory)
        with factory() as db, pytest.raises(DomainError) as rejected:
            load_history(db, 'tenant-a', history['snapshot']['change_id'])
        assert rejected.value.status_code == 409
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()


@pytest.mark.parametrize('malformed_adapter', [False, True])
def test_unselected_registrations_preserve_selected_approval(tmp_path, malformed_adapter):
    factory, history = approved_with_model_and_prompt(tmp_path)
    try:
        with factory.begin() as db:
            for cls, name in ((m.ModelSnapshot, 'model'), (m.PromptSnapshot, 'prompt'), (m.AdapterSnapshot, 'adapter')):
                payload = deepcopy(history['refs']['adapters'][0] if name == 'adapter' else history['refs'][name])
                payload.update(id=str(uuid4()), description='Unrelated registered version')
                add_payload(db, cls, payload)
            if malformed_adapter:
                db.add(m.AdapterSnapshot(tenant_id='tenant-a', id=str(uuid4()), schema_version='adapter_v1',
                    canonical_payload=b'{"broken":', payload_sha256='f' * 64))
        before = dump(factory)
        with factory() as db:
            loaded = load_history(db, 'tenant-a', history['snapshot']['change_id'])
        assert loaded['refs']['model'] == history['refs']['model']
        assert loaded['refs']['prompt'] == history['refs']['prompt']
        assert loaded['refs']['adapters'] == history['refs']['adapters']
        assert loaded['assessment'] == history['assessment'] and loaded['envelope'] == history['envelope']
        assert [run['run_config_sha256'] for run in loaded['runs']] == [run['run_config_sha256'] for run in history['runs']]
        assert verify_evidence(loaded)['historical_integrity'] == 'VALID'
        assert dump(factory) == before
    finally:
        factory.kw['bind'].dispose()
