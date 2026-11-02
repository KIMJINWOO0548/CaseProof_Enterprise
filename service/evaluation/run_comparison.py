"""Read-only projections of fully validated saved v2 runs.

Callers authorize and validate the entire history before projecting. Digests are
computed over the original payload; projected fields contain no historical text
or private evaluator values. Outcomes are descriptive, never a quality ranking.
"""
from service.api.errors import DomainError
from service.domain.canonical import content_hash

HISTORY_LIMIT = 100
CASE_LIMIT = 1000
VERSION_FIELDS = ('candidate_snapshot_id', 'source_bundle_id', 'dataset_version_id',
                  'suite_version_id', 'evaluator_version_id', 'adapter_version_id')
RESULT_FIELDS = ('verdict', 'complete', 'resolution_status', 'error_code', 'critical_failure')
DIMENSIONS = ('presence_changed', 'input_changed', 'output_changed', 'source_refs_changed', 'result_state_changed')


def summarize_run(run):
    return {**{key: run[key] for key in ('id', 'recorded_revision', 'created_at', 'completion',
             'gate_summary', 'run_input_sha256', 'run_config_sha256', *VERSION_FIELDS)},
            'payload_sha256': content_hash('evaluation-run', run)}


def summarize_history(runs):
    ordered = sorted(runs, key=lambda run: (-run['recorded_revision'], run['id']))
    return dict(schema='evaluation_run_history_v1', runs=[summarize_run(run) for run in ordered[:HISTORY_LIMIT]],
                total_runs=len(runs), limit=HISTORY_LIMIT, truncated=len(runs) > HISTORY_LIMIT)


def _case(case):
    if case is None:
        return None
    return {**{key: case[key] for key in (*RESULT_FIELDS, 'input_sha256', 'output_sha256')},
            'source_refs': [dict(id=ref['id'], payload_sha256=ref['payload_sha256'])
                            for ref in sorted(case['source_refs'], key=lambda ref: (ref['id'], ref['payload_sha256']))]}


def compare_runs(baseline, candidate):
    left = {case['case_id']: case for case in baseline['case_results']}
    right = {case['case_id']: case for case in candidate['case_results']}
    case_ids = left.keys() | right.keys()
    if len(case_ids) > CASE_LIMIT:
        raise DomainError('COMPARISON_LIMIT_EXCEEDED')
    counts = dict.fromkeys((*DIMENSIONS, 'any_changed'), 0)
    rows = []
    for case_id in sorted(case_ids):
        a, b = _case(left.get(case_id)), _case(right.get(case_id))
        shared = a is not None and b is not None
        changes = dict(presence_changed=not shared,
            input_changed=shared and a['input_sha256'] != b['input_sha256'],
            output_changed=shared and a['output_sha256'] != b['output_sha256'],
            source_refs_changed=shared and a['source_refs'] != b['source_refs'],
            result_state_changed=shared and any(a[key] != b[key] for key in RESULT_FIELDS))
        for key, changed in changes.items():
            counts[key] += int(changed)
        counts['any_changed'] += int(any(changes.values()))
        rows.append(dict(case_id=case_id, baseline=a, candidate=b, changes=changes))
    reasons = []
    if left.keys() != right.keys():
        reasons.append('CASE_SET_CHANGED')
    if baseline['run_config_sha256'] != candidate['run_config_sha256']:
        reasons.append('CONFIG_CHANGED')
    if baseline['run_input_sha256'] != candidate['run_input_sha256'] or counts['input_changed']:
        reasons.append('INPUT_CHANGED')
    if counts['source_refs_changed']:
        reasons.append('SOURCE_REFS_CHANGED')
    if any(baseline[key] != candidate[key] for key in VERSION_FIELDS):
        reasons.append('VERSION_CHANGED')
    mode = ('INCOMPLETE' if any(run['completion'] != 'COMPLETE' for run in (baseline, candidate))
            else 'CONTEXT_CHANGED' if reasons else 'SAME_CONTEXT')
    return dict(schema='evaluation_comparison_v1', baseline=summarize_run(baseline),
                candidate=summarize_run(candidate), mode=mode, context_reasons=reasons,
                changed_counts=counts, rows=rows)
