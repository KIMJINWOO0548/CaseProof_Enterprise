"""Independent temporal and scope expectations for fictional G3 policies."""
import copy
import json
from pathlib import Path

import pytest

from service.policies.resolver import resolve_context
from service.policies.schema import PolicyPack


@pytest.fixture
def pack():
    return json.loads(Path('datasets/packs/fictional_harbor.json').read_text(encoding='utf-8'))


@pytest.fixture
def context():
    return dict(tenant_id='fictional', pack_id='harbor', product_id='paper',
                workflow='review', rule_key='window', contract_date='2025-01-01',
                incident_date='2025-04-01', claim_date='2025-06-01',
                consultation_date='2025-07-01', rider_context_status='CONFIRMED', riders=[])


ASOF = '2025-08-01T00:00:00Z'


def test_resolves_required_basis_and_normalizes_asof(pack, context):
    result = resolve_context(context, pack, '2025-08-01T09:00:00+09:00')
    assert result['status'] == 'RESOLVED'
    assert result['basis_date'] == '2025-04-01'
    assert result['recorded_as_of'] == '2025-08-01T00:00:00.000000Z'
    assert (result['value'], result['source_id'], result['clause_id']) == (12, 'harbor-source', 'H-1')


@pytest.mark.parametrize('field', ['contract_date', 'incident_date'])
def test_missing_required_date_holds(pack, context, field):
    context.pop(field)
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'


def test_half_open_business_and_recorded_boundaries(pack, context):
    rule = pack['rules'][0]
    rule['valid_to'] = '2025-04-01'
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'
    context['incident_date'] = '2025-03-31'
    rule['recorded_to'] = ASOF
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'
    assert resolve_context(context, pack, '2025-07-31T23:59:59Z')['status'] == 'RESOLVED'


@pytest.mark.parametrize('start,end', [('2025-01-01','2025-01-01'),('2025-02-01','2025-01-01')])
def test_bad_business_interval_rejected(pack, start, end):
    pack['rules'][0].update(valid_from=start, valid_to=end)
    with pytest.raises(ValueError):
        PolicyPack.model_validate(pack)


def test_approval_is_historical_not_latest(pack, context):
    pack['sources'][0]['approval_history'].append(dict(recorded_at='2025-09-01T00:00:00Z', status='REVOKED', evidence_id='revocation-1'))
    assert resolve_context(context, pack, ASOF)['status'] == 'RESOLVED'
    assert resolve_context(context, pack, '2025-09-01T00:00:00Z')['status'] == 'INCONCLUSIVE'


def test_ambiguity_and_unreviewed_retroactivity_hold(pack, context):
    other = copy.deepcopy(pack['rules'][0])
    other.update(rule_id='different', value=99)
    pack['rules'].append(other)
    assert 'POLICY_CONFLICT' in resolve_context(context, pack, ASOF)['reason_codes']
    pack['rules'].pop()
    pack['rules'][0]['retroactive'] = True
    pack['retroactivity_policies'][0]['reviewed'] = False
    assert 'POLICY_CONFLICT' in resolve_context(context, pack, ASOF)['reason_codes']


@pytest.mark.parametrize('value', ['2025-01-01', '2025-01-01T00:00:00', '2025-01-01T24:00:00Z', '2025-01-01T00:00:00+24:00'])
def test_bad_recorded_time_holds(pack, context, value):
    assert resolve_context(context, pack, value)['status'] == 'INCONCLUSIVE'
    pack['rules'][0]['recorded_from'] = value
    with pytest.raises(ValueError):
        PolicyPack.model_validate(pack)


def test_recorded_interval_rejected_and_start_is_inclusive(pack, context):
    pack['rules'][0]['recorded_to'] = '2025-01-01T09:00:00+09:00'
    with pytest.raises(ValueError):
        PolicyPack.model_validate(pack)
    pack['rules'][0]['recorded_to'] = None
    assert resolve_context(context, pack, '2025-01-01T00:00:00Z')['status'] == 'RESOLVED'
    assert resolve_context(context, pack, '2024-12-31T23:59:59Z')['status'] == 'INCONCLUSIVE'


def test_workflows_choose_their_versioned_dates(pack, context):
    pack['workflows'][0].update(date_basis='claim_date', required_dates=['claim_date'], date_basis_version='basis-v2')
    pack['rules'][0]['valid_from'] = '2025-05-01'
    result = resolve_context(context, pack, ASOF)
    assert result['status'] == 'RESOLVED'
    assert result['basis_date'] == '2025-06-01'
    pack['workflows'][0].update(date_basis='consultation_date', required_dates=['consultation_date'])
    assert resolve_context(context, pack, ASOF)['basis_date'] == '2025-07-01'
    pack['workflows'][0].update(date_basis='contract_date', required_dates=['contract_date'])
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'


def test_asof_contradiction_and_strict_validation(pack, context):
    context['recorded_as_of'] = '2025-07-01T00:00:00Z'
    assert resolve_context(context, pack, ASOF)['reason_codes'] == ['CONTRADICTING_CONTEXT']
    context.pop('recorded_as_of')
    pack['rules'][0]['value'] = True
    with pytest.raises(ValueError):
        PolicyPack.model_validate(pack)


def test_source_reference_and_priority_review_fail_closed(pack, context):
    pack['rules'][0]['source_id'] = 'unknown-source'
    assert resolve_context(context, pack, ASOF)['reason_codes'] == ['INVALID_PACK']
    pack['rules'][0]['source_id'] = 'harbor-source'
    pack['priorities']['approved'] = False
    assert resolve_context(context, pack, ASOF)['reason_codes'] == ['POLICY_CONFLICT']
