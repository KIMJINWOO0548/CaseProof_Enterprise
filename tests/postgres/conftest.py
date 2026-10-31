"""Real disposable PostgreSQL only; credentials never enter test output."""
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from scripts.pg_test_bootstrap import disposable_database


def tenant_b_id(value):
    """Make all synthetic B references distinct without changing the A fixtures."""
    from uuid import UUID
    import hashlib
    if value in ('analyst', 'reviewer', 'approver'):
        return value + '-b'
    try:
        UUID(value)
    except (ValueError, TypeError, AttributeError):
        return value
    return str(UUID(bytes=hashlib.sha256(('pg-b:' + value).encode()).digest()[:16], version=4))


@pytest.fixture(scope='session')
def pg_database():
    admin_url = os.environ.get('CASEPROOF_PG_ADMIN_URL')
    config = Path('.runtime/g1-g6/postgres/test-config.json')
    if not admin_url and config.exists():
        admin_url = json.loads(config.read_text(encoding='utf-8'))['admin_url']
    if not admin_url:
        pytest.skip('Real PG17 unavailable: set CASEPROOF_PG_ADMIN_URL or private runtime config')
    with disposable_database(admin_url) as database:
        yield database


@pytest.fixture(scope='session')
def pg_owner_engine(pg_database):
    engine = create_engine(pg_database.owner_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope='session')
def pg_engine(pg_database):
    engine = create_engine(pg_database.app_url, pool_size=8, max_overflow=0)
    yield engine
    engine.dispose()


@pytest.fixture(scope='session')
def pg_seed(pg_database, tmp_path_factory):
    from tests.v1.helpers import setup
    from service.models_v1 import BaseV1
    from sqlalchemy import select
    source, actors, body = setup(tmp_path_factory.mktemp('pg-seed'))
    owner = create_engine(pg_database.owner_url)
    with source() as db:
        seed = {table.name: [dict(row._mapping) for row in db.execute(select(table))]
                for table in BaseV1.metadata.tables.values()}
    from service.domain.canonical import canonical_bytes, content_hash, parse_json
    from service.repositories import PURPOSES
    purposes = {model.__table__.name: purpose for model, purpose in PURPOSES.items()}
    def translate(value, hashes):
        if isinstance(value, dict):
            return {key: translate(item, hashes) for key, item in value.items()}
        if isinstance(value, list):
            return [translate(item, hashes) for item in value]
        return ('tenant-b' if value == 'tenant-a' else hashes.get(value, tenant_b_id(value))) if isinstance(value, str) else value
    # Resolve the seed's source/policy hash references before copying canonical bytes.
    hashes = {}
    for _ in range(len(seed)):
        updated = {row['payload_sha256']: content_hash(purposes[name], translate(parse_json(row['canonical_payload']), hashes))
                   for name, rows in seed.items() for row in rows if 'canonical_payload' in row}
        if updated == hashes:
            break
        hashes = updated
    for tenant in ('tenant-a', 'tenant-b'):
        with owner.begin() as connection:
            connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {'tenant': tenant})
            for table in BaseV1.metadata.tables.values():
                for row in seed[table.name]:
                    row = dict(row)
                    if tenant == 'tenant-b':
                        row = {key: tenant_b_id(value) if isinstance(value, str) and key != 'payload_sha256' else value for key, value in row.items()}
                    if tenant == 'tenant-b' and 'canonical_payload' in row:
                        payload = translate(parse_json(row['canonical_payload']), hashes)
                        row['canonical_payload'] = canonical_bytes(payload)
                        row['payload_sha256'] = content_hash(purposes[table.name], payload)
                    row['id' if table.name == 'v1_tenant' else 'tenant_id'] = tenant
                    connection.execute(table.insert().values(**row))
    owner.dispose()
    source.kw['bind'].dispose()
    return actors, body


@pytest.fixture(scope='session')
def pg_factory(pg_engine, pg_seed):
    return sessionmaker(pg_engine, expire_on_commit=False)


@pytest.fixture(scope='session')
def pg_populated(pg_database, pg_factory, pg_seed):
    from service.commands import execute_command
    from service.domain.types import ActorContext
    from service import models_v1 as m
    from service.repositories import add_payload
    from service.auth import tenant_context
    from tests.v1.helpers import pending_release, command
    from uuid import uuid4
    actors, body = pg_seed
    owner = create_engine(pg_database.owner_url)
    try:
        for tenant in ('tenant-a', 'tenant-b'):
            with sessionmaker(owner).begin() as db:
                tenant_context(db, tenant)
                for model, schema in ((m.ModelSnapshot, 'model_v1'), (m.PromptSnapshot, 'prompt_v1')):
                    add_payload(db, model, {'tenant_id': tenant, 'id': str(uuid4()), 'schema': schema})
            scoped = {name: ActorContext(tenant, tenant_b_id(actor.actor_id) if tenant == 'tenant-b' else actor.actor_id, actor.roles) for name, actor in actors.items()}
            scoped_body = {key: tenant_b_id(value) if tenant == 'tenant-b' else value for key, value in body.items()}
            identity = pending_release(pg_factory, scoped, scoped_body)
            result = execute_command(pg_factory, scoped['approver'], command({'decision': 'APPROVE', 'reason': 'Synthetic release accepted'}, 'release-decision', identity, 4))
            assert result.result_revision == 5
    finally:
        owner.dispose()
