import asyncio
import hashlib
import json
import httpx
import pytest
from fastapi import FastAPI
from service.api.v1 import build_router
from service.auth import DemoTokenAuthenticator
from tests.v1.helpers import setup


def client_app(tmp_path):
    factory, actors, body = setup(tmp_path)
    registry = {hashlib.sha256(name.encode()).hexdigest(): {'tenant_id': actor.tenant_id, 'actor_id': actor.actor_id} for name, actor in actors.items()}
    app = FastAPI()
    app.include_router(build_router(factory, DemoTokenAuthenticator(registry)))
    return app, factory, body


def request(app, method, path, body=None, headers=None, raw=None):
    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.request(method, path, content=raw if raw is not None else json.dumps(body).encode(),
                headers=headers or {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'http_test_key_123', 'Content-Type': 'application/json'})
    return asyncio.run(call())


def test_actual_create_replay_and_recovery(tmp_path):
    app, factory, body = client_app(tmp_path)
    first = request(app, 'POST', '/api/v1/changes', body)
    assert first.status_code == 201, first.text
    second = request(app, 'POST', '/api/v1/changes', body)
    assert second.status_code == 201 and second.json()['replayed'] is True
    assert first.json()['data'] == second.json()['data']
    recovered = request(app, 'GET', '/api/v1/mutations/http_test_key_123')
    assert recovered.status_code == 200 and recovered.json()['original_status'] == 201
    assert recovered.json()['data'] == first.json()['data']


@pytest.mark.parametrize('raw', [b'{"title":"one","title":"two"}', b'{"x":NaN}', b'{"x":"\\ud800"}', b'\xff'])
def test_raw_json_invalid(tmp_path, raw):
    app, factory, body = client_app(tmp_path)
    response = request(app, 'POST', '/api/v1/changes', raw=raw)
    assert response.status_code == 422 and response.json()['error']['code'] == 'INVALID_REQUEST'


@pytest.mark.parametrize('field', ['tenant_id', 'actor_id', 'roles', 'expected_revision'])
def test_untrusted_body_fields(tmp_path, field):
    app, factory, body = client_app(tmp_path)
    response = request(app, 'POST', '/api/v1/changes', dict(body, **{field: 'untrusted'}))
    assert response.status_code == 422


@pytest.mark.parametrize('headers', [
    {'Authorization': 'Bearer analyst'},
    {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'short'},
    {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'http_test_key_123', 'X-Expected-Revision': '1'},
    [('Authorization', 'Bearer analyst'), ('Idempotency-Key', 'http_test_key_123'), ('idempotency-key', 'http_test_key_123')],
])
def test_create_header_contract(tmp_path, headers):
    app, factory, body = client_app(tmp_path)
    assert request(app, 'POST', '/api/v1/changes', body, headers).status_code == 422


def test_authentication_and_cross_tenant_not_found(tmp_path):
    app, factory, body = client_app(tmp_path)
    assert request(app, 'POST', '/api/v1/changes', body, {'Authorization': 'Bearer missing'}).status_code == 401
    assert request(app, 'GET', '/api/v1/changes/12345678-1234-4234-8234-123456789012').status_code == 404


@pytest.mark.parametrize('value', [True, 30.0, '30'])
def test_http_claim_days_strict(tmp_path, value):
    app, factory, body = client_app(tmp_path)
    created = request(app, 'POST', '/api/v1/changes', body).json()['data']['change_id']
    response = request(app, 'POST', f'/api/v1/changes/{created}/evaluation-runs',
        {'suite_version_id': body['suite_version_id'], 'case_inputs': [{'case_id': 'case-a', 'claim_days': value, 'case_context': {}}]},
        {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'evaluation_key_123', 'X-Expected-Revision': '1'})
    assert response.status_code == 422


@pytest.mark.parametrize('revision', ['01', '0', '+1', '1.0', ' 1', '9007199254740992'])
def test_mutation_revision_headers(tmp_path, revision):
    app, factory, body = client_app(tmp_path)
    response = request(app, 'POST', '/api/v1/changes/12345678-1234-4234-8234-123456789012/submit', {},
        {'Authorization': 'Bearer analyst', 'Idempotency-Key': 'submit_test_key_123', 'X-Expected-Revision': revision})
    assert response.status_code == 422


def test_openapi_actual_routes_and_forbidden_extras(tmp_path):
    app, factory, body = client_app(tmp_path)
    schema = app.openapi()
    assert len(schema['paths']) == 8
    create = schema['paths']['/api/v1/changes']['post']
    assert create['requestBody']['content']['application/json']['schema']['additionalProperties'] is False
    assert [p['name'] for p in create['parameters']] == ['Idempotency-Key']


def test_openapi_declares_bearer_security(tmp_path):
    app, _, _ = client_app(tmp_path)
    schema = app.openapi()
    assert schema["paths"]["/api/v1/changes"]["post"]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
