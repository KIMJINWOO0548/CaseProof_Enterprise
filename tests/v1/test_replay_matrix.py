"""HTTP retries bind the original route, resource and revision before freshness."""
import pytest

from tests.v1.helpers import dump
from tests.v1.test_http import client_app, request


def headers(key, revision=None):
    value = {'Authorization': 'Bearer analyst', 'Idempotency-Key': key}
    if revision is not None:
        value['X-Expected-Revision'] = str(revision)
    return value


@pytest.mark.parametrize('changed', ['route', 'resource', 'revision'])
def test_same_actor_key_conflict_matrix_has_no_effect(tmp_path, changed):
    app, factory, body = client_app(tmp_path)
    identities = [request(app, 'POST', '/api/v1/changes', body,
                          headers(f'matrix_create_key_{index}')).json()['data']['change_id']
                  for index in (1, 2)]
    payload = {'suite_version_id': body['suite_version_id'], 'case_inputs': [
        {'case_id': case, 'claim_days': 30, 'case_context': {}} for case in ('case-a', 'case-b')]}
    path = f'/api/v1/changes/{identities[0]}/evaluation-runs'
    key = 'matrix_evaluation_key'
    original = request(app, 'POST', path, payload, headers(key, 1))
    assert original.status_code == 201, original.text
    before = dump(factory)

    conflicting_path, conflicting_body, revision = path, payload, 1
    if changed == 'route':
        conflicting_path = f'/api/v1/changes/{identities[0]}/submit'
        conflicting_body, revision = {}, 2
    elif changed == 'resource':
        conflicting_path = f'/api/v1/changes/{identities[1]}/evaluation-runs'
    else:
        revision = 2
    response = request(app, 'POST', conflicting_path, conflicting_body, headers(key, revision))
    assert response.status_code == 409, response.text
    assert response.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert dump(factory) == before

    replay = request(app, 'POST', path, payload, headers(key, 1))
    assert replay.status_code == 201 and replay.json()['replayed'] is True
    assert replay.json()['data'] == original.json()['data']
    assert replay.json()['result_revision'] == original.json()['result_revision'] == 2
    assert dump(factory) == before
