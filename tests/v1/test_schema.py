"""Real SQLite constraint/migration tests; payload fixtures do not claim valid history."""
import hashlib
import json
import sqlite3
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError

from service.models_v1 import BaseV1, IMMUTABLE_TABLES, MAX_INTEGER

ROOT = Path(__file__).resolve().parents[2]
TABLES = BaseV1.metadata.tables


def config():
    return Config(str(ROOT / 'alembic.ini'))


@pytest.fixture(scope='session')
def migrated_template(tmp_path_factory):
    path = tmp_path_factory.mktemp('v1-schema') / 'template.db'
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('CASEPROOF_V1_DATABASE_URL', 'sqlite:///' + path.as_posix())
        patch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
        command.upgrade(config(), 'head')
    return path


@pytest.fixture
def database(tmp_path, monkeypatch, migrated_template):
    path = tmp_path / 'disposable.db'
    url = 'sqlite:///' + path.as_posix()
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', url)
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    shutil.copyfile(migrated_template, path)
    engine = create_engine(url)

    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')

    yield engine, path
    engine.dispose()


def row(table, tenant='a'):
    result = {}
    for col in table.columns:
        name = col.name
        if name == 'tenant_id':
            value = tenant
        elif name == 'canonical_payload' or name == 'roles_payload':
            value = b'{}'
        elif name == 'schema_version':
            value = 'relational_test_fixture_v1'
        elif name.endswith('sha256'):
            value = tenant * 64
        elif name == 'enabled':
            value = True
        elif name == 'status':
            value = 'DRAFT'
        elif name == 'stage':
            value = 'DOMAIN'
        elif name == 'original_status':
            value = 201
        elif name in ('revision_to', 'output_revision', 'approved_revision', 'recorded_revision', 'result_revision'):
            value = 2
        elif name in ('revision', 'revision_from', 'input_revision', 'preapproval_revision', 'sequence'):
            value = 1
        elif name == 'key':
            value = 'fixture_key_123'
        else:
            value = tenant
        result[name] = value
    return result


def rows(table, tenant):
    data = row(table, tenant)
    if table.name == 'v1_change_revision':
        return [data, dict(data, revision=2)]
    return [data]


def seed(engine, override=None):
    # Deliberately insert children before parents. All cycles resolve at commit.
    with engine.begin() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
        connection.execute(TABLES['v1_tenant'].insert(), [{'id': 'a'}, {'id': 'b'}])
        for tenant in ('b', 'a'):
            for table in reversed(list(TABLES.values())):
                if table.name == 'v1_tenant':
                    continue
                for index, data in enumerate(rows(table, tenant)):
                    if override:
                        data = override(table, tenant, index, data)
                    connection.execute(table.insert().values(**data))


def test_schema_is_separate():
    from service.models import Base
    assert BaseV1.metadata is not Base.metadata
    assert all(name.startswith('v1_') for name in TABLES)
    assert not any(fk.referred_table.name == 'v1_change_revision' for fk in TABLES['v1_change'].foreign_key_constraints)


def test_migration_roundtrip_and_metadata(database):
    engine, _ = database
    command.check(config())
    with engine.connect() as connection:
        actual = inspect(connection)
        for name, table in TABLES.items():
            assert set(c['name'] for c in actual.get_columns(name)) == set(table.c.keys())
            assert set(actual.get_pk_constraint(name)['constrained_columns']) == set(c.name for c in table.primary_key)
    command.downgrade(config(), 'base')
    command.upgrade(config(), 'head')
    command.check(config())


def test_deferred_genesis_order_and_rollback(database):
    engine, _ = database
    seed(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    with pytest.raises(RuntimeError, match='injected'):
        with engine.begin() as connection:
            connection.execute(TABLES['v1_tenant'].insert().values(id='rollback'))
            connection.execute(TABLES['v1_actor'].insert().values(tenant_id='rollback', id='rollback', enabled=True, roles_payload=b'[]'))
            connection.execute(TABLES['v1_change'].insert().values(**dict(row(TABLES['v1_change'], 'rollback'), revision=0, status='INCOMPLETE')))
            raise RuntimeError('injected genesis failure')
    with engine.connect() as connection:
        for table in TABLES.values():
            key = table.c.id if table.name == 'v1_tenant' else table.c.tenant_id
            assert connection.execute(select(table).where(key == 'rollback')).first() is None


COMPOSITE_FKS = [(name, tuple(fk.column_keys)) for name, table in TABLES.items()
                 for fk in table.foreign_key_constraints if len(fk.column_keys) > 1]


@pytest.mark.parametrize('name,columns', COMPOSITE_FKS)
def test_every_reference_rejects_other_tenant(database, name, columns):
    engine, _ = database
    foreign_column = next(col for col in columns if col != 'tenant_id')

    def cross_tenant(table, tenant, index, data):
        if table.name == name and tenant == 'a' and index == 0:
            data[foreign_column] = 'b' * 64 if foreign_column.endswith('sha256') else 'b'
        return data

    with pytest.raises(IntegrityError, match='FOREIGN KEY constraint failed'):
        seed(engine, cross_tenant)
    with engine.connect() as connection:
        assert connection.execute(select(TABLES['v1_tenant'])).first() is None


@pytest.mark.parametrize('name,change', [
    ('v1_change_transition', {'id': 'duplicate'}),
    ('v1_decision_note', {'id': 'duplicate'}),
    ('v1_evaluation_run', {'id': 'duplicate'}),
    ('v1_audit_event', {'id': 'duplicate'}),
    ('v1_idempotency_record', {'id': 'duplicate'}),
    ('v1_assessment', {'id': 'duplicate', 'payload_sha256': 'c' * 64}),
    ('v1_approval_envelope', {'id': 'duplicate', 'payload_sha256': 'c' * 64}),
])
def test_required_uniqueness(database, name, change):
    engine, _ = database
    seed(engine)
    with pytest.raises(IntegrityError, match='UNIQUE constraint failed'):
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP TRIGGER {name}_no_replace')
            connection.execute(TABLES[name].insert().values(**(row(TABLES[name]) | change)))


BOUNDED_COLUMNS = [(name, column.name) for name, table in TABLES.items() for column in table.c
                   if column.name in {'revision', 'revision_from', 'revision_to', 'input_revision', 'output_revision',
                                      'recorded_revision', 'result_revision', 'preapproval_revision', 'approved_revision', 'sequence'}]


@pytest.mark.parametrize('name,column', BOUNDED_COLUMNS)
@pytest.mark.parametrize('value', [-1, 1.5, MAX_INTEGER + 1])
def test_safe_integer_bounds(database, name, column, value):
    engine, _ = database
    with pytest.raises(IntegrityError, match='CHECK constraint failed'):
        with engine.begin() as connection:
            connection.execute(TABLES[name].insert().values(**(row(TABLES[name]) | {column: value})))


@pytest.mark.parametrize('name', IMMUTABLE_TABLES)
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_sql_immutable_records(database, name, operation):
    engine, _ = database
    seed(engine)
    table = TABLES[name]
    statement = table.delete() if operation == 'delete' else table.update().values(tenant_id='a')
    with pytest.raises(IntegrityError, match='append-only'):
        with engine.begin() as connection:
            connection.execute(statement.where(table.c.tenant_id == 'a'))


def test_skeleton_cannot_claim_approval(database):
    engine, _ = database
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(TABLES['v1_change'].insert().values(**(row(TABLES['v1_change']) | {'revision': 0, 'status': 'APPROVED_FOR_DEMO'})))


@pytest.mark.parametrize('name', list(TABLES))
def test_downgrade_refuses_any_populated_table(database, name):
    engine, path = database
    # Simulate even an orphaned/corrupted database: guard must preserve every table.
    with sqlite3.connect(path) as connection:
        data = row(TABLES[name])
        columns = ','.join('"' + key + '"' for key in data)
        placeholders = ','.join('?' for _ in data)
        connection.execute(f'INSERT INTO "{name}" ({columns}) VALUES ({placeholders})', list(data.values()))
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match='populated'):
        command.downgrade(config(), 'base')
    assert path.read_bytes() == before


def test_baseline_refused_without_touching_bytes(tmp_path, monkeypatch):
    from service.models import Base
    path = tmp_path / 'baseline.db'
    url = 'sqlite:///' + path.as_posix()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as connection:
        baseline_tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', url)
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    with pytest.raises(RuntimeError, match='legacy-unverified'):
        command.upgrade(config(), 'head')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == baseline_tables
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'v1_%'").fetchall()


@pytest.mark.parametrize('mode,url', [(None, 'sqlite://'), ('production', 'sqlite://'), ('disposable', None),
                                    ('disposable', 'postgresql://localhost/disposable')])
def test_migration_requires_explicit_disposable_sqlite(monkeypatch, mode, url):
    for key, value in [('CASEPROOF_V1_MIGRATION_MODE', mode), ('CASEPROOF_V1_DATABASE_URL', url)]:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        command.upgrade(config(), 'head')


def test_canonical_payload_preserves_all_contract_properties(database):
    from service.domain.canonical import canonical_bytes, content_hash
    engine, _ = database
    seed(engine)
    schema_files = ['change-revision', 'change-transition', 'audit-event', 'decision-note',
                    'evaluation-run', 'assessment-manifest', 'approval-envelope']
    for name in schema_files:
        schema = json.loads((ROOT / 'contracts' / (name + '.schema.json')).read_text(encoding='utf-8'))
        assert set(schema['required']) == set(schema['properties'])
        # Storage is lossless; validation and projection comparison are separate G1.3 work.
        payload = {key: None for key in schema['properties']}
        data = row(TABLES['v1_source_snapshot']) | {'id': name, 'canonical_payload': canonical_bytes(payload),
                                                  'payload_sha256': content_hash('storage-test', payload)}
        with engine.begin() as connection:
            connection.execute(TABLES['v1_source_snapshot'].insert().values(**data))
        with engine.connect() as connection:
            stored = connection.execute(select(TABLES['v1_source_snapshot']).where(TABLES['v1_source_snapshot'].c.id == name)).mappings().one()
            assert json.loads(stored['canonical_payload']) == payload
            assert stored['payload_sha256'] == content_hash('storage-test', payload)


def test_migration_ddl_failure_rolls_back(tmp_path, monkeypatch):
    from sqlalchemy.engine import Engine
    path = tmp_path / 'interrupted.db'
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', 'sqlite:///' + path.as_posix())
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    count = 0

    def fail_third_create(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        if statement.lstrip().upper().startswith('CREATE TABLE'):
            count += 1
            if count == 3:
                raise RuntimeError('injected DDL failure')

    event.listen(Engine, 'before_cursor_execute', fail_third_create)
    try:
        with pytest.raises(RuntimeError, match='injected DDL'):
            command.upgrade(config(), 'head')
    finally:
        event.remove(Engine, 'before_cursor_execute', fail_third_create)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    command.upgrade(config(), 'head')


@pytest.mark.parametrize('name,changes', [
    ('v1_source_snapshot', {'canonical_payload': b'{"tampered":true}'}),
    ('v1_change_transition', {'id': 'replacement'}),
    ('v1_decision_note', {'id': 'replacement'}),
    ('v1_change', {'status': 'APPROVED_FOR_DEMO'}),
])
def test_insert_or_replace_cannot_erase_records(database, name, changes):
    engine, _ = database
    seed(engine)
    with pytest.raises(IntegrityError, match='append-only'):
        with engine.begin() as connection:
            assert connection.exec_driver_sql('PRAGMA recursive_triggers').scalar() == 0
            connection.execute(TABLES[name].insert().prefix_with('OR REPLACE').values(**(row(TABLES[name]) | changes)))
