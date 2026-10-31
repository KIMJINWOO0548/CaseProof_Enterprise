"""Persisted full-suite outcomes, including adapter failure and latest-run veto."""
from copy import deepcopy
from uuid import uuid4

import pytest

from service.api.errors import DomainError
from service.commands import execute_command
from service.domain.canonical import content_hash
from service.evaluation.runner import prepare_run
from service.repositories import load_history
from tests.v1.helpers import command, dump, setup


def inputs(body, days=30):
    return {'suite_version_id': body['suite_version_id'], 'case_inputs': [
        {'case_id': name, 'claim_days': days, 'case_context': {}} for name in ('case-a', 'case-b')]}


@pytest.mark.parametrize('case_ids', [['case-a'], ['case-a', 'case-a'], ['case-a', 'unknown']])
def test_full_suite_rejects_wrong_case_set(tmp_path, case_ids):
    factory, actors, body = setup(tmp_path)
    identity = execute_command(factory, actors['analyst'], command(body)).data['change_id']
    before = dump(factory)
    payload = inputs(body)
    payload['case_inputs'] = [{'case_id': name, 'claim_days': 30, 'case_context': {}} for name in case_ids]
    with pytest.raises(DomainError, match='INVALID_REQUEST'):
        execute_command(factory, actors['analyst'], command(payload, 'evaluation-runs', identity, 1))
    assert dump(factory) == before


def test_new_complete_pass_preserves_failure_and_allows_submit(tmp_path):
    factory, actors, body = setup(tmp_path)
    identity = execute_command(factory, actors['analyst'], command(body)).data['change_id']
    first = execute_command(factory, actors['analyst'], command(inputs(body, 29), 'evaluation-runs', identity, 1))
    assert first.status_code == 201 and first.data['run']['gate_summary'] == 'BLOCK'
    second = execute_command(factory, actors['analyst'], command(inputs(body), 'evaluation-runs', identity, 2))
    assert second.data['run']['gate_summary'] == 'PASS'
    submitted = execute_command(factory, actors['analyst'], command({}, 'submit', identity, 3))
    assert submitted.data['status'] == 'PENDING_DOMAIN_REVIEW'
    with factory() as db:
        history = load_history(db, 'tenant-a', identity)
    assert [r['gate_summary'] for r in history['runs']] == ['BLOCK', 'PASS']


def test_adapter_timeout_commits_incomplete_and_vetoes_older_pass(tmp_path, monkeypatch):
    from service.evaluation.adapters import FakeDeterministicAdapter
    factory, actors, body = setup(tmp_path)
    identity = execute_command(factory, actors['analyst'], command(body)).data['change_id']
    execute_command(factory, actors['analyst'], command(inputs(body), 'evaluation-runs', identity, 1))
    original = FakeDeterministicAdapter.execute

    def timeout(self, case):
        if case['case_id'] == 'case-b':
            raise TimeoutError('Do not persist raw exception text')
        return original(self, case)

    monkeypatch.setattr(FakeDeterministicAdapter, 'execute', timeout)
    result = execute_command(factory, actors['analyst'], command(inputs(body), 'evaluation-runs', identity, 2))
    assert result.status_code == 201 and result.data['run']['completion'] == 'INCOMPLETE'
    assert result.data['run']['case_results'][1]['error_code'] == 'ADAPTER_TIMEOUT'
    with pytest.raises(DomainError, match='EVALUATION_INCOMPLETE'):
        execute_command(factory, actors['analyst'], command({}, 'submit', identity, 3))
    with factory() as db:
        history = load_history(db, 'tenant-a', identity)
    assert len(history['runs']) == 2 and history['snapshot']['active_run_id'] == result.data['run']['id']


def test_policy_source_registered_id_resolves_to_uuid_snapshot(tmp_path):
    import json
    from pathlib import Path
    factory, actors, body = setup(tmp_path)
    identity = execute_command(factory, actors['analyst'], command(body)).data['change_id']
    with factory() as db:
        history = deepcopy(load_history(db, 'tenant-a', identity))
    pack = json.loads((Path(__file__).parents[2] / 'datasets/packs/fictional_harbor.json').read_text())
    pack.update(tenant_id='tenant-a', pack_id='pack', product_ids=['product'])
    pack['workflows'][0]['workflow'] = 'claims'
    pack['rules'][0].update(product_id='product', workflow='claims', rule_key='days', value=30)
    source = history['refs']['sources'][0]
    source.update(source_id='harbor-source', policy_version_id='v1', value=30)
    history['refs']['sources'] = [source]
    history['refs']['policies'][0]['pack_snapshot'] = pack
    history['refs']['suite'].update(required_case_ids=['case-a'], case_policy_versions={'case-a': ['v1']},
                                    minimum_distinct_policy_versions=1)
    history['refs']['source_eligibility'][0]['source_refs'] = [dict(id=source['id'],
        payload_sha256=content_hash('source', source), policy_version_id='v1', status='APPROVED')]
    context = dict(contract_date='2025-02-01', incident_date='2025-02-02', rider_context_status='CONFIRMED',
                   riders=[], recorded_as_of='2025-03-01T00:00:00.000000Z')
    run = prepare_run(history, {'suite_version_id': body['suite_version_id'], 'case_inputs': [
        {'case_id': 'case-a', 'claim_days': 30, 'case_context': context}]}, actors['analyst'],
        str(uuid4()), '2026-10-31T00:00:00.000000Z', 2)
    assert run['gate_summary'] == 'PASS'
    assert run['case_results'][0]['source_refs'][0]['id'] == source['id']
