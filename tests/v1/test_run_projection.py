"""Independent fixed saved-result fixtures for the pure bounded projection."""
from copy import deepcopy
from importlib import import_module, util

import pytest

from service.api.errors import DomainError


def projector():
    assert util.find_spec('service.evaluation.run_comparison'), 'saved-run projector is not implemented'
    return import_module('service.evaluation.run_comparison')


def run():
    return dict(schema='evaluation_run_v2', id='00000000-0000-4000-8000-000000000001',
        recorded_revision=2, created_at='2026-01-01T00:00:00.000000Z',
        completion='COMPLETE', gate_summary='PASS', run_input_sha256='1' * 64,
        run_config_sha256='2' * 64, candidate_snapshot_id='candidate', source_bundle_id='bundle',
        dataset_version_id='dataset', suite_version_id='suite', evaluator_version_id='evaluator',
        adapter_version_id='adapter', case_results=[dict(case_id='a', input_sha256='3' * 64,
        output_sha256='4' * 64, source_refs=[dict(id='source-b', payload_sha256='b' * 64),
        dict(id='source-a', payload_sha256='a' * 64)], resolution_status='RESOLVED',
        verdict='PASS', complete=True, error_code=None, critical_failure=False)])


def pair():
    a = run()
    b = deepcopy(a)
    b['id'] = '00000000-0000-4000-8000-000000000002'
    return a, b


def test_output_only_is_same_context_and_source_refs_are_sorted_without_mutation():
    a, b = pair()
    b['case_results'][0]['output_sha256'] = '5' * 64
    original = deepcopy((a, b))
    result = projector().compare_runs(a, b)
    assert result['mode'] == 'SAME_CONTEXT' and result['context_reasons'] == []
    assert result['changed_counts'] == dict(presence_changed=0, input_changed=0, output_changed=1,
        source_refs_changed=0, result_state_changed=0, any_changed=1)
    assert [ref['id'] for ref in result['rows'][0]['baseline']['source_refs']] == ['source-a', 'source-b']
    assert (a, b) == original


def test_incomplete_keeps_context_and_missing_sides_and_never_borrows_pass():
    a, b = pair()
    b.update(completion='INCOMPLETE', gate_summary='BLOCK', run_config_sha256='6' * 64,
             suite_version_id='different-suite')
    case = b['case_results'][0]
    case.update(case_id='b', verdict='INCONCLUSIVE', complete=False,
                resolution_status='INCONCLUSIVE', error_code='ADAPTER_TIMEOUT', critical_failure=None)
    result = projector().compare_runs(a, b)
    assert result['mode'] == 'INCOMPLETE'
    assert result['context_reasons'] == ['CASE_SET_CHANGED', 'CONFIG_CHANGED', 'VERSION_CHANGED']
    assert [r['case_id'] for r in result['rows']] == ['a', 'b']
    assert result['rows'][0]['candidate'] is None and result['rows'][1]['baseline'] is None
    assert result['rows'][1]['candidate']['verdict'] == 'INCONCLUSIVE'
    assert result['rows'][1]['candidate']['error_code'] == 'ADAPTER_TIMEOUT'
    assert result['changed_counts']['presence_changed'] == result['changed_counts']['any_changed'] == 2
    assert result['changed_counts']['input_changed'] == 0  # no shared row to compare


@pytest.mark.parametrize('field,value,reason', [('input_sha256', '7' * 64, 'INPUT_CHANGED'),
    ('source_refs', [dict(id='new-source', payload_sha256='8' * 64)], 'SOURCE_REFS_CHANGED')])
def test_input_and_sources_are_context_changes(field, value, reason):
    a, b = pair()
    b['case_results'][0][field] = value
    result = projector().compare_runs(a, b)
    assert result['mode'] == 'CONTEXT_CHANGED' and result['context_reasons'] == [reason]


def test_same_incomplete_run_has_zero_change_reasons():
    a = run()
    a.update(completion='INCOMPLETE', gate_summary='BLOCK')
    a['case_results'][0].update(verdict='INCONCLUSIVE', complete=False,
        error_code='ADAPTER_ERROR', critical_failure=None)
    result = projector().compare_runs(a, a)
    assert result['mode'] == 'INCOMPLETE' and result['context_reasons'] == []
    assert set(result['changed_counts'].values()) == {0}


def test_union_limit_is_inclusive_and_has_no_unsafe_details():
    a, b = pair()
    a['case_results'] = [dict(a['case_results'][0], case_id=f'case-{i:04}') for i in range(1000)]
    b['case_results'] = []
    assert len(projector().compare_runs(a, b)['rows']) == 1000
    b['case_results'] = [dict(run()['case_results'][0], case_id='extra')]
    with pytest.raises(DomainError, match='COMPARISON_LIMIT_EXCEEDED') as raised:
        projector().compare_runs(a, b)
    assert raised.value.status_code == 422 and raised.value.details == {}


def test_history_limit_uses_revision_not_timestamp_and_preserves_source_digest():
    records = []
    for i in range(101):
        records.append(dict(run(), id=f'00000000-0000-4000-8000-{i:012}', recorded_revision=i+2))
    records[-1]['created_at'] = '2020-01-01T00:00:00.000000Z'
    before = deepcopy(records)
    result = projector().summarize_history(records)
    assert result['schema'] == 'evaluation_run_history_v1'
    assert (result['total_runs'], result['limit'], result['truncated']) == (101, 100, True)
    assert [item['recorded_revision'] for item in result['runs']] == list(range(102, 2, -1))
    assert records == before
