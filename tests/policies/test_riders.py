import copy

from test_bitemporal import ASOF, context, pack
from service.policies.resolver import resolve_context


def test_confirmed_empty_and_unknown(pack, context):
    assert resolve_context(context, pack, ASOF)['status'] == 'RESOLVED'
    context['rider_context_status'] = 'UNKNOWN'
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'


def test_unknown_or_unapproved_rider_never_falls_back(pack, context):
    context['riders'] = [dict(code='extra', enrolled_from='2025-01-01', enrolled_to=None,
                              confirmation_evidence_id='12345678-1234-4234-8234-123456789abc')]
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'
    rider = copy.deepcopy(pack['rules'][0])
    rider.update(rule_id='rider-rule', rider_code='extra', priority_key='rider', source_id='rider-source')
    pack['rules'].append(rider)
    pack['sources'].append(dict(source_id='rider-source', policy_version='v1', approval_history=[
        dict(recorded_at='2025-01-01T00:00:00Z', status='DRAFT', evidence_id='draft-1')]))
    result = resolve_context(context, pack, ASOF)
    assert result['status'] == 'INCONCLUSIVE'
    assert 'SOURCE_NOT_APPROVED' in result['reason_codes']
    pack['sources'][1]['approval_history'][0]['status'] = 'APPROVED'
    assert resolve_context(context, pack, ASOF)['rule_id'] == 'rider-rule'
    context['riders'][0]['confirmation_evidence_id'] = None
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'


def test_duplicate_conflicting_rider_facts_hold(pack, context):
    rider = dict(code='extra', enrolled_from='2025-01-01', enrolled_to=None,
                 confirmation_evidence_id='12345678-1234-4234-8234-123456789abc')
    context['riders'] = [rider, dict(rider, enrolled_to='2025-02-01')]
    assert 'CONTRADICTING_CONTEXT' in resolve_context(context, pack, ASOF)['reason_codes']
