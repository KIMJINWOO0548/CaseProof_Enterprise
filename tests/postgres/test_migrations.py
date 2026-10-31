import pytest
from sqlalchemy import create_engine, inspect, text
from scripts.pg_test_bootstrap import migrate, grant_runtime
from service.models_v1 import BaseV1


def test_frozen_schema_matches_columns_and_composite_foreign_keys(pg_database):
    engine = create_engine(pg_database.owner_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == set(BaseV1.metadata.tables) | {'caseproof_pg_alembic_version'}
        for table in BaseV1.metadata.tables.values():
            assert {c['name'] for c in inspector.get_columns(table.name)} == set(table.c.keys())
            actual = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns'])) for f in inspector.get_foreign_keys(table.name)}
            expected = {(tuple(c.parent.name for c in f.elements), f.elements[0].column.table.name, tuple(c.column.name for c in f.elements)) for f in table.foreign_key_constraints}
            assert actual == expected
    finally:
        engine.dispose()


def test_empty_database_downgrade_upgrade(pg_database, pg_engine):
    # A separate fresh database avoids depending on test ordering or deleting seed data.
    from scripts.pg_test_bootstrap import disposable_database
    # The outer database owner cannot create databases; reuse the private admin configuration.
    import os, json
    from pathlib import Path
    admin = os.environ.get('CASEPROOF_PG_ADMIN_URL')
    if not admin:
        admin = json.loads(Path('.runtime/g1-g6/postgres/test-config.json').read_text(encoding='utf-8'))['admin_url']
    with disposable_database(admin) as fresh:
        migrate(fresh.owner_url, 'base')
        engine = create_engine(fresh.owner_url)
        try:
            assert inspect(engine).get_table_names() == ['caseproof_pg_alembic_version']
        finally:
            engine.dispose()
        migrate(fresh.owner_url)
        grant_runtime(fresh.owner_url, fresh.app_role)
        engine = create_engine(fresh.app_url)
        try:
            with engine.connect() as db:
                assert db.execute(text('SELECT count(*) FROM v1_actor')).scalar_one() == 0
        finally:
            engine.dispose()


def test_populated_downgrade_refuses_and_preserves_schema(pg_database, pg_seed):
    with pytest.raises(RuntimeError, match='empty disposable'):
        migrate(pg_database.owner_url, 'base')
    engine = create_engine(pg_database.app_url)
    try:
        with engine.connect() as db:
            policies = db.execute(text("SELECT count(*) FROM pg_class WHERE relname LIKE 'v1_%' AND relkind='r' AND relrowsecurity AND relforcerowsecurity")).scalar_one()
            assert policies == len(BaseV1.metadata.tables)
    finally:
        engine.dispose()
