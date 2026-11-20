"""Independent expectations for an invented internal document-review specification.

These tests do not encode a regulator's deadline or an investment conclusion.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from service.policies import PackRegistry, resolve_context


PACK_PATH = Path('datasets/packs/synthetic_securities_review.json')
ASOF = '2025-08-01T00:00:00Z'


@pytest.fixture
def securities_pack():
    return json.loads(PACK_PATH.read_text(encoding='utf-8'))


@pytest.fixture
def review_context():
    return dict(tenant_id='fictional', pack_id='securities-review-synthetic',
                product_id='synthetic-bond-memo', workflow='document-review',
                rule_key='internal-review-window', consultation_date='2025-07-01',
                rider_context_status='CONFIRMED', riders=[])


@pytest.mark.parametrize('review_date,expected', [
    ('2024-12-31', None), ('2025-01-01', 10), ('2025-06-30', 10),
    ('2025-07-01', 7), ('2025-07-02', 7),
])
def test_synthetic_review_specification_boundary(securities_pack, review_context, review_date, expected):
    review_context['consultation_date'] = review_date
    result = resolve_context(review_context, securities_pack, ASOF)
    if expected is None:
        assert result['status'] == 'INCONCLUSIVE' and result['value'] is None
    else:
        assert (result['status'], result['value'], result['unit']) == ('RESOLVED', expected, 'days')
        assert (result['date_basis'], result['basis_date']) == ('consultation_date', review_date)
        version = 'v1' if expected == 10 else 'v2'
        assert (result['source_id'], result['policy_version'], result['clause_id']) == (
            'synthetic-memo-' + version, version, 'SYNTHETIC-INTERNAL-' + version)


@pytest.mark.parametrize('asof,expected', [
    ('2025-05-31T23:59:59.999999Z', 'INCONCLUSIVE'),
    ('2025-06-01T00:00:00Z', 'RESOLVED'),
    ('2025-09-01T00:00:00Z', 'INCONCLUSIVE'),
])
def test_source_history_uses_requested_knowledge_time(securities_pack, review_context, asof, expected):
    result = resolve_context(review_context, securities_pack, asof)
    assert result['status'] == expected
    if expected == 'INCONCLUSIVE':
        assert result['value'] is None
        assert 'SOURCE_NOT_APPROVED' in result['candidates'][1]['reason_codes']


def test_recorded_interval_is_half_open(securities_pack, review_context):
    securities_pack['rules'][1]['recorded_from'] = ASOF
    before = resolve_context(review_context, securities_pack, '2025-07-31T23:59:59.999999Z')
    assert before['status'] == 'INCONCLUSIVE'
    assert 'OUTSIDE_RECORDED_INTERVAL' in before['candidates'][1]['reason_codes']
    assert resolve_context(review_context, securities_pack, ASOF)['value'] == 7
    securities_pack['rules'][1]['recorded_from'] = '2025-05-15T00:00:00Z'
    securities_pack['rules'][1]['recorded_to'] = ASOF
    assert resolve_context(review_context, securities_pack, '2025-07-31T23:59:59.999999Z')['value'] == 7
    result = resolve_context(review_context, securities_pack, ASOF)
    assert result['status'] == 'INCONCLUSIVE'
    assert 'OUTSIDE_RECORDED_INTERVAL' in result['candidates'][1]['reason_codes']


@pytest.mark.parametrize('field', ['tenant_id', 'pack_id', 'product_id', 'workflow', 'rule_key'])
def test_synthetic_pack_cannot_cross_scope(securities_pack, review_context, field):
    review_context[field] = 'different-scope'
    result = resolve_context(review_context, securities_pack, ASOF)
    assert result['status'] == 'INCONCLUSIVE'
    assert result['reason_codes'] == ['NO_RULE_IN_SCOPE']


def test_review_date_and_confirmed_context_cannot_be_inferred(securities_pack, review_context):
    review_context.pop('consultation_date')
    review_context['incident_date'] = '2025-07-01'
    result = resolve_context(review_context, securities_pack, ASOF)
    assert result['reason_codes'] == ['MISSING_REQUIRED_DATE']
    assert result['required_fields'] == ['consultation_date']
    review_context['consultation_date'] = '2025-07-01'
    review_context['rider_context_status'] = 'UNKNOWN'
    assert resolve_context(review_context, securities_pack, ASOF)['reason_codes'] == ['UNKNOWN_RIDER_CONTEXT']


def test_registers_alongside_unchanged_insurance_fixtures(securities_pack, review_context):
    registry = PackRegistry()
    insurance_values = {'harbor': 12, 'orchard': 18, 'lantern': 24}
    for pack_id, expected in insurance_values.items():
        pack = json.loads(Path('datasets/packs/fictional_' + pack_id + '.json').read_text(encoding='utf-8'))
        registry.register(pack)
        context = dict(tenant_id='fictional', pack_id=pack_id, product_id='paper',
                       workflow='review', rule_key='window', contract_date='2025-01-01',
                       incident_date='2025-04-01', rider_context_status='CONFIRMED', riders=[])
        assert resolve_context(context, registry.get('fictional', pack_id), ASOF)['value'] == expected
    registered = registry.register(securities_pack)
    registered['sources'].clear()
    assert resolve_context(review_context, registry.get('fictional', 'securities-review-synthetic'), ASOF)['value'] == 7
    assert registry.list_packs('fictional') == ['harbor', 'lantern', 'orchard', 'securities-review-synthetic']
    with pytest.raises(KeyError):
        registry.get('another-tenant', 'securities-review-synthetic')
    modified = deepcopy(securities_pack)
    modified['rules'][1]['value'] = 99
    with pytest.raises(ValueError, match='new version'):
        registry.register(modified)


def test_unknown_source_and_unapproved_priority_hold(securities_pack, review_context):
    securities_pack['rules'][1]['source_id'] = 'nonexistent-source'
    assert resolve_context(review_context, securities_pack, ASOF)['reason_codes'] == ['INVALID_PACK']
    securities_pack['rules'][1]['source_id'] = 'synthetic-memo-v2'
    securities_pack['priorities']['approved'] = False
    assert resolve_context(review_context, securities_pack, ASOF)['reason_codes'] == ['POLICY_CONFLICT']
