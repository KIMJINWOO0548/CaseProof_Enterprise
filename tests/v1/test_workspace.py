"""Actual standalone workspace endpoints with disposable migrated SQLite."""
import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from service.db import make_engine, session_factory
from service.workspace import create_workspace_app, seed_workspace


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    url = 'sqlite:///' + (tmp_path / 'workspace.db').as_posix()
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', url)
    command.upgrade(Config('alembic.ini'), 'head')
    engine = make_engine(url)
    factory = session_factory(engine)
    with factory.begin() as db:
        seed_workspace(db)
        seed_workspace(db, 'other')
    registry = {hashlib.sha256(('test-' + role).encode()).hexdigest(): {'tenant_id': 'fictional', 'actor_id': role}
                for role in ('analyst', 'reviewer', 'approver', 'auditor')}
    registry[hashlib.sha256(b'test-other').hexdigest()] = {'tenant_id': 'other', 'actor_id': 'analyst'}
    monkeypatch.setenv('CASEPROOF_DEMO_MODE', '1')
    with TestClient(create_workspace_app(factory, registry)) as client:
        yield client, factory, registry
    engine.dispose()


def headers(actor='analyst'):
    return {'Authorization': 'Bearer test-' + actor}


def mutate(client, path, body, revision=None, actor='analyst'):
    h = headers(actor) | {'Idempotency-Key': 'workspace_' + uuid4().hex}
    if revision is not None:
        h['X-Expected-Revision'] = str(revision)
    response = client.post('/api/v1/changes' + path, json=body, headers=h)
    assert response.status_code in (200, 201), response.text
    return response.json()['data']


def test_registered_packs_and_third_pack_approval(workspace):
    client, factory, _ = workspace
    assert client.get('/v1').status_code == 200
    assert client.get('/static/v1.js').status_code == 200
    metadata = client.get('/api/v1/workspace', headers=headers()).json()['data']
    assert metadata['capabilities'] == {'external_model': False, 'external_anchor': False, 'synthetic': True}
    presets = metadata['presets']
    assert [p['pack_id'] for p in presets] == ['harbor', 'orchard', 'lantern']
    for preset in presets:
        change = mutate(client, '', preset['create_body'])
        run = mutate(client, '/' + change['change_id'] + '/evaluation-runs',
                     {'suite_version_id': change['suite_version_id'], 'case_inputs': preset['case_inputs']}, 1)
        assert run['run']['gate_summary'] == 'PASS'
    identity = change['change_id']
    mutate(client, '/' + identity + '/submit', {}, 2)
    mutate(client, '/' + identity + '/domain-decision', {'decision': 'APPROVE', 'reason': 'Independent synthetic domain review'}, 3, 'reviewer')
    approved = mutate(client, '/' + identity + '/release-decision', {'decision': 'APPROVE', 'reason': 'Independent synthetic release review'}, 4, 'approver')
    assert approved['status'] == 'APPROVED_FOR_DEMO'
    evidence = client.get('/api/v1/changes/' + identity + '/evidence', headers=headers('auditor')).json()['data']
    assert evidence['historical_integrity'] == 'VALID'
    assert evidence['external_anchor'] == 'NOT_CONFIGURED'
    listing = client.get('/api/v1/changes', headers=headers()).json()['data']
    assert len(listing) == 3
    assert all(row['tenant_id'] == 'fictional' for row in listing)
    assert client.get('/api/v1/changes', headers={'Authorization': 'Bearer test-other'}).json()['data'] == []
    assert client.get('/api/v1/changes/' + identity, headers={'Authorization': 'Bearer test-other'}).status_code == 404


def test_workspace_auth_revocation_and_demo_boundary(workspace, monkeypatch):
    from service import models_v1 as m
    client, factory, registry = workspace
    for path in ('/api/v1/workspace', '/api/v1/changes'):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'Authorization': 'Bearer unknown'}).status_code == 401
    with factory.begin() as db:
        db.get(m.Actor, ('fictional', 'analyst')).enabled = False
    assert client.get('/api/v1/workspace', headers=headers()).status_code == 401
    monkeypatch.delenv('CASEPROOF_DEMO_MODE')
    with pytest.raises(RuntimeError, match='DEMO_MODE'):
        create_workspace_app(factory, registry)


def test_font_response_is_portable_and_preserves_upstream_bytes(workspace, monkeypatch):
    from starlette import responses
    client, _, _ = workspace
    monkeypatch.setattr(responses, 'guess_type', lambda *args, **kwargs: ('application/octet-stream', None))
    response = client.get('/static/vendor/suit/SUIT-Variable.woff2')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'font/woff2'
    assert hashlib.sha256(response.content).hexdigest() == 'aa894a204d5a6fbae259dac6868d350cbd373a390caee0313f92946af741df23'
