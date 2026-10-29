"""HTTP and OpenAPI assertions for the G1 input contract."""
import pytest
from test_service import fx, auth, create, evaluate, ready_for_domain


@pytest.mark.parametrize('value', [True, False, 1.0, '30', -1, 10000])
def test_claim_days_rejects_non_integer_or_out_of_range_json(fx, value):
    client, _ = fx
    response = evaluate(client, create(client), claim_days=value)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize('value', [0, 30, 9999])
def test_claim_days_accepts_bounded_json_integers(fx, value):
    client, _ = fx
    assert evaluate(client, create(client), claim_days=value).status_code == 201


def test_openapi_declares_required_reason_and_strict_integer_policy(fx):
    client, _ = fx
    schemas = client.get('/openapi.json').json()['components']['schemas']
    decision = schemas['Decision']
    assert 'reason' in decision['required']
    reason = decision['properties']['reason']
    assert (reason['minLength'], reason['maxLength']) == (8, 500)
    assert 'strip' in reason['description']
    claim = schemas['EvalRequest']['properties']['claim_days']
    assert (claim['type'], claim['minimum'], claim['maximum']) == ('integer', 0, 9999)
    assert claim['x-strict-json-integer'] is True


@pytest.mark.parametrize('reason', [None, '', ' ' * 8, '1234567 ', 'x' * 501, ' ' + 'x' * 500])
def test_decision_rejects_missing_or_invalid_reason(fx, reason):
    client, _ = fx
    change = ready_for_domain(client)
    body = {'expected_revision': change['revision'], 'decision': 'APPROVE'}
    if reason is not None:
        body['reason'] = reason
    response = client.post(f"/api/changes/{change['id']}/domain-decision",
                           headers=auth('aurora-reviewer'), json=body)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize('reason', ['  검토근거를확인했습니다  ', '😀' * 8, '가' * 500])
def test_decision_stores_trimmed_unicode_reason(fx, reason):
    client, _ = fx
    change = ready_for_domain(client)
    response = client.post(f"/api/changes/{change['id']}/domain-decision",
                           headers=auth('aurora-reviewer'),
                           json={'expected_revision': change['revision'],
                                 'decision': 'APPROVE', 'reason': reason})
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/changes/{change['id']}", headers=auth('aurora-analyst')).json()
    assert detail['decisions'][0]['reason'] == reason.strip()
