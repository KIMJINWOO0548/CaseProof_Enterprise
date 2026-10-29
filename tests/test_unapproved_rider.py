"""A selected but unapproved applicable rider must not silently use the base rule."""
from copy import deepcopy

import pytest

from reference.resolver import load_rules, resolve


def query():
    return {'tenant': 'AURORA_NONLIFE', 'product': 'AUTO-101',
            'workflow': 'AUTO_CLAIM_GUIDANCE', 'rule_key': 'DOCUMENT_WINDOW_DAYS',
            'claim_received_date': '2026-06-30', 'as_of_recorded': '2026-10-28T00:00:00+09:00',
            'rider_codes': ['PENDING_RIDER']}


@pytest.mark.parametrize('state', ['DRAFT', 'REVOKED'])
def test_selected_unapproved_rider_is_inconclusive(state):
    rules = load_rules()
    rider = deepcopy(next(r for r in rules if r['rule_id'] == 'AR-AUTO-2026-H1'))
    rider.update(rule_id='PENDING-RIDER-1', rider='PENDING_RIDER', source_state=state,
                 priority=1000, value=999)
    rules.append(rider)
    before = deepcopy(rules)
    result = resolve(query(), rules)
    assert result.status == 'INCONCLUSIVE'
    assert result.reason_codes == ['SOURCE_NOT_APPROVED']
    assert result.value is None
    assert rules == before


def test_unselected_draft_rider_does_not_change_known_base_case():
    rules = load_rules()
    rider = deepcopy(next(r for r in rules if r['rule_id'] == 'AR-AUTO-2026-H1'))
    rider.update(rule_id='UNSELECTED-1', rider='PENDING_RIDER', source_state='DRAFT', value=999)
    rules.append(rider)
    result = resolve({**query(), 'rider_codes': []}, rules)
    assert result.status == 'RESOLVED'
    assert result.value == 30
