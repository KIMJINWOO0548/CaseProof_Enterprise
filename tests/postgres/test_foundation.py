from pathlib import Path
import re


def test_frozen_postgres_migration_has_no_sqlite_or_live_metadata():
    sql = Path('migrations/postgres/versions/0001_schema.sql').read_text()
    assert 'CREATE TABLE v1_actor' in sql
    assert 'typeof(' not in sql and 'GLOB' not in sql
    assert 'DEFERRABLE INITIALLY DEFERRED' in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'FORCE ROW LEVEL SECURITY' in sql
    assert "current_setting('app.tenant_id', true)" in sql
    revision = Path('migrations/postgres/versions/0001_pg.py').read_text()
    assert 'models_v1' not in revision and 'create_all' not in revision


def test_database_name_guard():
    from scripts.pg_test_bootstrap import validate_database_name
    for name in ('postgres', 'caseproof', 'caseproof_test_', 'caseproof_test_a;DROP DATABASE postgres'):
        import pytest
        with pytest.raises(ValueError):
            validate_database_name(name)
    validate_database_name('caseproof_test_ab123456')
