"""Create a fresh PG17 test database; never reset the database named in the admin URL."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import secrets
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def validate_database_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'caseproof_test_[a-f0-9]{8,32}', name):
        raise ValueError('Refusing a database without a generated disposable test name')


@dataclass(frozen=True)
class TestDatabase:
    name: str
    owner_url: object
    app_url: object
    owner_role: str
    app_role: str


def migrate(owner_url, target='head'):
    config = Config(str(ROOT / 'alembic-postgres.ini'))
    engine = create_engine(owner_url)
    try:
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            if target == 'base':
                command.downgrade(config, target)
            else:
                command.upgrade(config, target)
    finally:
        engine.dispose()


def grant_runtime(owner_url, app_role):
    engine = create_engine(owner_url)
    try:
        with engine.begin() as connection:
            quoted = connection.dialect.identifier_preparer.quote_identifier(app_role)
            connection.exec_driver_sql('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO {quoted}')
            tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'v1_%' ORDER BY tablename")).scalars()
            for table in tables:
                identifier = connection.dialect.identifier_preparer.quote_identifier(table)
                connection.exec_driver_sql(f'GRANT SELECT ON {identifier} TO {quoted}')
                if table not in ('v1_tenant', 'v1_actor', 'v1_tenant_audit_head'):
                    connection.exec_driver_sql(f'GRANT INSERT ON {identifier} TO {quoted}')
            connection.exec_driver_sql(f'GRANT UPDATE ON v1_change TO {quoted}')
            connection.exec_driver_sql(f'GRANT UPDATE (sequence, head_sha256) ON v1_tenant_audit_head TO {quoted}')
    finally:
        engine.dispose()


def verify_runtime(app_url):
    engine = create_engine(app_url)
    try:
        with engine.connect() as connection:
            role = connection.execute(text('SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user')).one()
            owns = connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user) OR EXISTS(SELECT 1 FROM pg_database WHERE datname = current_database() AND datdba = (SELECT oid FROM pg_roles WHERE rolname=current_user))")).scalar_one()
            if any(role) or owns:
                raise RuntimeError('Runtime role must be a non-owner without administrative or BYPASSRLS powers')
    finally:
        engine.dispose()


@contextmanager
def disposable_database(admin_url):
    """Only resources created by this invocation are removed on exit."""
    from psycopg import sql

    url = make_url(admin_url)
    if url.get_backend_name() != 'postgresql':
        raise ValueError('A real PostgreSQL admin URL is required')
    url = url.set(drivername='postgresql+psycopg')
    if sys.platform == 'win32':
        # Local disposable Windows PG has no Kerberos; SSPI probing can fail with 10014.
        url = url.update_query_dict({'gssencmode': 'disable'})
    suffix = secrets.token_hex(8)
    name = 'caseproof_test_' + suffix
    owner, app = 'cp_owner_' + suffix, 'cp_app_' + suffix
    owner_password, app_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    validate_database_name(name)
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    created_roles, created_db = [], False
    try:
        with admin.connect() as connection:
            raw = connection.connection.driver_connection
            for role, password in ((owner, owner_password), (app, app_password)):
                raw.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))
                created_roles.append(role)
            raw.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name), sql.Identifier(owner)))
            created_db = True
            raw.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
            raw.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(name), sql.Identifier(app)))
        owner_url = url.set(database=name, username=owner, password=owner_password)
        app_url = url.set(database=name, username=app, password=app_password)
        migrate(owner_url)
        grant_runtime(owner_url, app)
        verify_runtime(app_url)
        yield TestDatabase(name, owner_url, app_url, owner, app)
    finally:
        with admin.connect() as connection:
            raw = connection.connection.driver_connection
            if created_db:
                raw.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            for role in reversed(created_roles):
                raw.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
        admin.dispose()
