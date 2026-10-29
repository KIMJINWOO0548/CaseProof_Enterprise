"""Paired, sealed-snapshot comparison for risk of new critical failures.

This reference deliberately does not pretend to measure real LLM quality:
its cases are supplied by external reviewed evaluators.
"""
from __future__ import annotations
from math import sqrt


def wilson_interval(success: int, total: int, z: float = 1.96):
    if total <= 0 or not (0 <= success <= total):
        raise ValueError('invalid denominator or count')
    p = success / total
    denom = 1 + z*z/total
    mid = (p + z*z/(2*total))/denom
    half = (z/denom) * sqrt(p*(1-p)/total + z*z/(4*total*total))
    return [round(max(0., mid-half), 4), round(min(1., mid+half), 4)]


def compare_runs(baseline: dict, candidate: dict) -> dict:
    """Compare complete pairs only; ``critical`` means observed critical failure.

    Per-arm Wilson intervals are descriptive, not a paired-difference interval.
    Incomplete or malformed runs return INVALID without accuracy statistics.
    """
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        return {'status':'INVALID', 'reasons':['INVALID_RUN_STRUCTURE']}
    required_keys = ('dataset_hash','evaluator_hash')
    if any(not baseline.get(k) or baseline.get(k) != candidate.get(k) for k in required_keys):
        return {'status':'INVALID', 'reasons':['SNAPSHOT_NOT_COMPARABLE']}
    for run in (baseline, candidate):
        rows = run.get('cases')
        if not isinstance(rows, list) or any(
            not isinstance(x, dict) or not isinstance(x.get('id'), str) or not x['id']
            for x in rows
        ):
            return {'status':'INVALID', 'reasons':['INVALID_RUN_STRUCTURE']}
    b = {x['id']:x for x in baseline['cases']}
    c = {x['id']:x for x in candidate['cases']}
    if len(b) != len(baseline['cases']) or len(c) != len(candidate['cases']) or not b or b.keys() != c.keys():
        return {'status':'INVALID','reasons':['PAIRED_CASE_IDS_MISMATCH']}
    n = len(b)
    if any(not isinstance(x.get('critical'), bool) or not isinstance(x.get('correct'), bool)
           or not isinstance(x.get('complete'), bool) for x in [*b.values(), *c.values()]):
        return {'status':'INVALID','reasons':['INVALID_CASE_LABELS']}
    incomplete_baseline = sorted(k for k in b if not b[k]['complete'])
    incomplete_candidate = sorted(k for k in c if not c[k]['complete'])
    if incomplete_baseline or incomplete_candidate:
        return {
            'status':'INVALID', 'reasons':['INCOMPLETE_EVALUATION'], 'case_count':n,
            'incomplete_baseline_ids':incomplete_baseline,
            'incomplete_candidate_ids':incomplete_candidate,
            'incomplete_ids':sorted(set(incomplete_baseline) | set(incomplete_candidate)),
        }
    new_critical = sorted(k for k in b if c[k]['critical'] and not b[k]['critical'])
    not_completed = sorted(k for k in c if not c[k]['complete'])
    b_success = sum(v['correct'] for v in b.values())
    c_success = sum(v['correct'] for v in c.values())
    reasons = []
    if new_critical: reasons.append('NEW_CRITICAL_REGRESSION')
    if not_completed: reasons.append('INCOMPLETE_EVALUATION')
    return {'status':'BLOCKED' if reasons else 'ELIGIBLE_FOR_HUMAN_REVIEW',
            'reasons':reasons,'case_count':n,
            'baseline_correct':b_success, 'candidate_correct':c_success,
            'accuracy_delta_pp':round(100*(c_success-b_success)/n,2),
            'baseline_wilson95':wilson_interval(b_success,n),
            'candidate_wilson95':wilson_interval(c_success,n),
            'new_critical_ids':new_critical, 'incomplete_ids':not_completed,
            'disagreements':sorted(k for k in b if b[k]['correct'] != c[k]['correct'])}
