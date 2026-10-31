"""Pure full-suite gate; current source eligibility is separate from old seals."""


def source_eligibility(history):
    rows = [row for row in history['refs']['source_eligibility']
            if row['source_bundle_id'] == history['snapshot']['source_bundle_id']]
    if not rows or any(type(row.get('sequence')) is not int or row['sequence'] < 1 for row in rows):
        return {'eligible': False, 'source_refs': []}
    latest = max(row['sequence'] for row in rows)
    selected = [row for row in rows if row['sequence'] == latest]
    return selected[0] if len(selected) == 1 else {'eligible': False, 'source_refs': []}


def check_run_gate(run, suite, eligibility):
    reasons = []
    cases = run['case_results']
    required = suite['required_case_ids']
    ids = [case['case_id'] for case in cases]
    exact = bool(required) and len(required) == len(set(required)) and sorted(ids) == sorted(set(required))
    complete = exact and all(case['complete'] is True for case in cases)
    if not complete:
        reasons.append('EVALUATION_INCOMPLETE')
    if any(case['verdict'] != 'PASS' or case['critical_failure'] is not False or case.get('error_code') is not None for case in cases):
        reasons.append('CASE_NOT_PASS')
    refs = eligibility.get('source_refs', [])
    source_map = {ref['id']: ref for ref in refs}
    source_ok = eligibility.get('eligible') is True and bool(refs) and len(source_map) == len(refs)
    versions, coverage = set(), set()
    for case in cases:
        allowed = suite.get('case_policy_versions', {}).get(case['case_id'], [])
        seen = set()
        if not case['source_refs'] or not allowed:
            source_ok = False
        for ref in case['source_refs']:
            source = source_map.get(ref['id'])
            if (source is None or source['status'] != 'APPROVED' or ref['id'] in seen
                    or source['payload_sha256'] != ref['payload_sha256']
                    or source['policy_version_id'] not in allowed):
                source_ok = False
            else:
                versions.add(source['policy_version_id'])
            seen.add(ref['id'])
        coverage.update(suite.get('coverage_by_case', {}).get(case['case_id'], []))
    if not source_ok:
        reasons.append('SOURCE_NOT_ELIGIBLE')
    minimum = suite.get('minimum_distinct_policy_versions')
    if type(minimum) is not int or minimum < 1 or len(versions) < minimum:
        reasons.append('INSUFFICIENT_POLICY_VERSION_COVERAGE')
    if not set(suite['required_coverage_labels']).issubset(coverage):
        reasons.append('INSUFFICIENT_CASE_COVERAGE')
    return dict(gate_summary='BLOCK' if reasons else 'PASS', completion='COMPLETE' if complete else 'INCOMPLETE',
                reasons=reasons, source_eligible=source_ok)
