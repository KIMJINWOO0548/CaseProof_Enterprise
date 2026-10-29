"""Incomplete pairs must never publish apparently final accuracy statistics."""
from copy import deepcopy

import pytest

from reference.paired_benchmark import compare_runs


def run():
    return {
        'dataset_hash': 'a' * 64,
        'evaluator_hash': 'b' * 64,
        'cases': [
            {'id': 'old-rule', 'critical': False, 'correct': True, 'complete': True},
            {'id': 'new-rule', 'critical': False, 'correct': False, 'complete': True},
        ],
    }


@pytest.mark.parametrize('side', ['baseline', 'candidate', 'both'])
def test_incomplete_pair_has_no_accuracy_or_confidence_interval(side):
    baseline, candidate = run(), run()
    if side in ('baseline', 'both'):
        baseline['cases'][0]['complete'] = False
    if side in ('candidate', 'both'):
        candidate['cases'][1]['complete'] = False
    report = compare_runs(baseline, candidate)
    assert report['status'] == 'INVALID'
    assert report['reasons'] == ['INCOMPLETE_EVALUATION']
    assert 'accuracy_delta_pp' not in report
    assert 'baseline_wilson95' not in report
    assert 'candidate_wilson95' not in report
    assert report['incomplete_baseline_ids'] == (['old-rule'] if side != 'candidate' else [])
    assert report['incomplete_candidate_ids'] == (['new-rule'] if side != 'baseline' else [])


@pytest.mark.parametrize('bad', [None, {}, {'cases': None}, {'cases': [None]}, {'cases': [{'id': []}]}])
def test_malformed_input_returns_invalid_without_crashing(bad):
    malformed = deepcopy(bad)
    if isinstance(malformed, dict):
        malformed.update(dataset_hash='a' * 64, evaluator_hash='b' * 64)
    assert compare_runs(malformed, run())['status'] == 'INVALID'


def test_complete_pairs_keep_hand_checked_counts():
    candidate = run()
    candidate['cases'][1]['correct'] = True
    result = compare_runs(run(), candidate)
    assert result['status'] == 'ELIGIBLE_FOR_HUMAN_REVIEW'
    assert result['baseline_correct'] == 1
    assert result['candidate_correct'] == 2
    assert result['accuracy_delta_pp'] == 50.0
    assert result['disagreements'] == ['new-rule']
