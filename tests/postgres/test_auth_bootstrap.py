import hashlib
import pytest
from sqlalchemy import create_engine, text
from service.auth import DemoTokenAuthenticator
from service.api.errors import DomainError


def authenticator(actor='analyst'):
    return DemoTokenAuthenticator({hashlib.sha256(b'synthetic-token').hexdigest(): {'tenant_id': 'tenant-a', 'actor_id': actor}})


def test_registry_then_current_database_identity(pg_factory):
    with pg_factory.begin() as db:
        assert db.execute(text('SELECT count(*) FROM v1_actor')).scalar_one() == 0
        actor = authenticator()('synthetic-token', db)
        assert actor.tenant_id == 'tenant-a' and actor.roles == frozenset({'ANALYST'})
        assert db.execute(text('SELECT DISTINCT tenant_id FROM v1_actor')).scalars().all() == ['tenant-a']


@pytest.mark.parametrize('token,actor', [('unknown', 'analyst'), ('synthetic-token', 'missing')])
def test_unknown_token_or_missing_actor_rejected(pg_factory, token, actor):
    with pg_factory.begin() as db:
        with pytest.raises(DomainError) as error:
            authenticator(actor)(token, db)
        assert error.value.code == 'UNAUTHENTICATED'


def test_disabled_actor_and_role_changes_authoritative(pg_database, pg_factory):
    owner = create_engine(pg_database.owner_url)
    try:
        for enabled, payload in [(False, b'["ANALYST"]'), (True, b'["AUDITOR"]')]:
            with owner.begin() as db:
                db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
                db.execute(text("UPDATE v1_actor SET enabled=:enabled,roles_payload=:payload WHERE id='analyst'"), {'enabled': enabled, 'payload': payload})
            with pg_factory.begin() as db:
                if not enabled:
                    with pytest.raises(DomainError):
                        authenticator()('synthetic-token', db)
                else:
                    assert authenticator()('synthetic-token', db).roles == frozenset({'AUDITOR'})
    finally:
        with owner.begin() as db:
            db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
            db.execute(text("UPDATE v1_actor SET enabled=true,roles_payload=:payload WHERE id='analyst'"), {'payload': b'["ANALYST"]'})
        owner.dispose()


def test_registry_duplicate_missing_or_malformed_startup_rejected():
    digest = hashlib.sha256(b'synthetic-token').hexdigest()
    entry = {'tenant_id': 'tenant-a', 'actor_id': 'analyst'}
    for registry in ({}, [(digest, entry), (digest, entry)], {'bad': entry}, {digest: {'tenant_id': ''}}):
        with pytest.raises(ValueError):
            DemoTokenAuthenticator(registry)
