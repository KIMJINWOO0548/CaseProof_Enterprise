"""Current source diagnostics must not be presented as approval authorization."""
from tests.v1.test_http import client_app, request


def test_source_eligibility_is_distinct_from_failed_run_and_submission(tmp_path):
    app, factory, body = client_app(tmp_path)
    try:
        created = request(app, 'POST', '/api/v1/changes', body)
        assert created.status_code == 201
        identity = created.json()['data']['change_id']
        evaluated = request(app, 'POST', f'/api/v1/changes/{identity}/evaluation-runs',
            {'suite_version_id': body['suite_version_id'], 'case_inputs': [
                {'case_id': case, 'claim_days': 29, 'case_context': {}}
                for case in ('case-a', 'case-b')]},
            {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'source_semantics_evaluate',
             'X-Expected-Revision': '1'})
        assert evaluated.status_code == 201
        assert evaluated.json()['data']['run']['gate_summary'] == 'BLOCK'
        submitted = request(app, 'POST', f'/api/v1/changes/{identity}/submit', {},
            {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'source_semantics_submit',
             'X-Expected-Revision': '2'})
        assert submitted.status_code == 409
        assert submitted.json()['error']['code'] == 'RELEASE_GATE_BLOCKED'
        response = request(app, 'GET', f'/api/v1/changes/{identity}/evidence')
        assert response.status_code == 200
        data = response.json()['data']
        # Preserve the historical field and its established source-only predicate.
        assert data['historical_integrity'] == 'VALID'
        assert data['current_approval_eligibility'] == 'ELIGIBLE'
        description = app.openapi()['paths']['/api/v1/changes/{change_id}/evidence']['get']['description']
        assert 'source eligibility only' in description
        assert 'does not authorize approval' in description
    finally:
        factory.kw['bind'].dispose()
