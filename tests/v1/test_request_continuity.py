"""Check request context across independent workspace starts and checked restores."""
import hashlib
import re
import shutil

import pytest

from service import models_v1 as m
from service.db import make_engine, session_factory
from service.domain.canonical import canonical_bytes
from service.recovery import backup_database, file_sha256, reactivate_reviewed_actors, restore_database
from service.workspace import create_workspace_app, seed_workspace
from tests.v1.helpers import dump, setup
from tests.v1.test_http import request
from tests.v1.test_contracts import assert_schema


HEADER = 'X-CaseProof-Request-Context'


def registry(**actors):
    return {
        hashlib.sha256(token.encode()).hexdigest(): {'tenant_id': identity[0], 'actor_id': identity[1]}
        for token, identity in actors.items()
    }


def context(app, token='analyst'):
    response = request(app, 'GET', '/api/v1/workspace', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()['data']['request_context']


def mutation_headers(token, value):
    return {'Authorization': 'Bearer ' + token, 'Idempotency-Key': 'synthetic_context_recovery_1', HEADER: value}


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv('CASEPROOF_DEMO_MODE', '1')
    factory, _, body = setup(tmp_path)
    with factory.begin() as db:
        seed_workspace(db, 'tenant-b')
    entries = registry(analyst=('tenant-a', 'analyst'), reviewer=('tenant-a', 'reviewer'),
                       other=('tenant-b', 'analyst'))
    try:
        yield tmp_path / 'v1.db', factory, body, entries
    finally:
        factory.kw['bind'].dispose()


def test_context_restarts_and_replays_only_for_the_original_actor(profile):
    path, factory, body, entries = profile
    first = create_workspace_app(factory, entries)
    expected = context(first)
    assert re.fullmatch(r'[0-9a-f]{64}', expected)
    assert len({expected, context(first, 'other'), context(first, 'reviewer')}) == 3
    headers = mutation_headers('analyst', expected)
    before = dump(factory)
    for token in ('other', 'reviewer'):
        denied = request(first, 'POST', '/api/v1/changes', body, mutation_headers(token, expected))
        assert denied.status_code == 409
        assert denied.json()['error']['code'] == 'REQUEST_CONTEXT_CHANGED'
        assert_schema(denied.json(), 'error.schema.json')
        assert dump(factory) == before

    saved = request(first, 'POST', '/api/v1/changes', body, headers)
    assert saved.status_code == 201 and saved.json()['replayed'] is False
    committed = dump(factory)
    factory.kw['bind'].dispose()
    engine = make_engine('sqlite:///' + path.as_posix())
    try:
        fresh_factory = session_factory(engine)
        restarted = create_workspace_app(fresh_factory, entries)
        assert context(restarted) == expected
        recovered = request(restarted, 'POST', '/api/v1/changes', body, headers)
        assert recovered.status_code == 201
        assert recovered.json() == {**saved.json(), 'replayed': True}
        conflict = request(restarted, 'POST', '/api/v1/changes', dict(body, title='Another synthetic title'), headers)
        assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
        assert dump(fresh_factory) == committed
        with fresh_factory.begin() as db:
            db.get(m.Actor, ('tenant-a', 'analyst')).roles_payload = canonical_bytes(['AUDITOR'])
        assert context(restarted) == expected
        after_revocation = dump(fresh_factory)
        denied = request(restarted, 'POST', '/api/v1/changes', body, headers)
        assert denied.status_code == 403 and denied.json()['error']['code'] == 'FORBIDDEN'
        assert 'data' not in denied.json()
        assert dump(fresh_factory) == after_revocation
    finally:
        engine.dispose()


def test_context_requires_one_value_and_follows_authentication(profile):
    _, factory, body, entries = profile
    app = create_workspace_app(factory, entries)
    value = context(app)
    duplicate = [*mutation_headers('analyst', value).items(), (HEADER.lower(), value)]
    before = dump(factory)
    assert request(app, 'POST', '/api/v1/changes', body, duplicate).status_code == 422
    assert request(app, 'POST', '/api/v1/changes', body, mutation_headers('unknown', value)).status_code == 401
    assert dump(factory) == before


def test_context_blocks_reexecution_when_checked_restore_predates_the_request(profile):
    path, factory, body, entries = profile
    app = create_workspace_app(factory, entries)
    expected = context(app)
    backup = path.with_name('previous.db')
    restored = path.with_name('restored.db')
    metadata = backup_database(path, backup)
    headers = mutation_headers('analyst', expected)
    assert request(app, 'POST', '/api/v1/changes', body, headers).status_code == 201
    with factory.begin() as db:
        db.get(m.Actor, ('tenant-a', 'reviewer')).enabled = False
    restore_database(backup, restored, metadata)

    engine = make_engine('sqlite:///' + restored.as_posix())
    try:
        fresh_factory = session_factory(engine)
        quarantined = create_workspace_app(fresh_factory, entries)
        assert request(quarantined, 'POST', '/api/v1/changes', body, headers).status_code == 401
        engine.dispose()
        rotated = registry(rotated=('tenant-a', 'analyst'))
        reactivate_reviewed_actors(restored, file_sha256(restored),
            [{'tenant_id': 'tenant-a', 'actor_id': 'analyst', 'roles': ['ANALYST']}],
            entries, rotated, 'synthetic current authorization review')
        restored_app = create_workspace_app(fresh_factory, rotated)
        assert context(restored_app, 'rotated') != expected
        before = dump(fresh_factory)
        assert not before['v1_change'] and not before['v1_idempotency_record']
        denied = request(restored_app, 'POST', '/api/v1/changes', body, mutation_headers('rotated', expected))
        assert denied.status_code == 409 and denied.json()['error']['code'] == 'REQUEST_CONTEXT_CHANGED'
        assert request(restored_app, 'GET', '/api/v1/workspace',
                       headers={'Authorization': 'Bearer reviewer'}).status_code == 401
        with fresh_factory() as db:
            assert not db.get(m.Actor, ('tenant-a', 'reviewer')).enabled
        assert dump(fresh_factory) == before
    finally:
        engine.dispose()


def test_running_app_does_not_bind_saved_or_new_intents_to_replacement_file(profile):
    path, factory, body, entries = profile
    running = create_workspace_app(factory, entries)
    old_context = context(running)
    factory.kw['bind'].dispose()
    original = path.with_name('original.db')
    path.rename(original)
    shutil.copyfile(original, path)
    fresh = create_workspace_app(factory, entries)
    new_context = context(fresh)
    assert new_context and new_context != old_context
    assert context(running) is None
    before = dump(factory)
    for value in (old_context, new_context):
        response = request(running, 'POST', '/api/v1/changes', body, mutation_headers('analyst', value))
        assert response.status_code == 409 and response.json()['error']['code'] == 'REQUEST_CONTEXT_CHANGED'
    assert dump(factory) == before
