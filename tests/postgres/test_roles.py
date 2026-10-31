from sqlalchemy import create_engine, text
from scripts.pg_test_bootstrap import verify_runtime
from service.models_v1 import IMMUTABLE_TABLES


def test_runtime_role_and_explicit_grants(pg_database, pg_engine):
    verify_runtime(pg_database.app_url)
    with pg_engine.connect() as db:
        assert db.execute(text('SELECT current_user')).scalar_one() == pg_database.app_role
        assert not db.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar_one()
        for table in IMMUTABLE_TABLES:
            for operation in ('SELECT', 'INSERT'):
                assert db.execute(text('SELECT has_table_privilege(current_user,:table,:operation)'), {'table': table, 'operation': operation}).scalar_one()
            for operation in ('UPDATE', 'DELETE', 'TRUNCATE'):
                assert not db.execute(text('SELECT has_table_privilege(current_user,:table,:operation)'), {'table': table, 'operation': operation}).scalar_one()
    owner = create_engine(pg_database.owner_url)
    try:
        with owner.connect() as db:
            assert db.execute(text("SELECT bool_and(tableowner=current_user) FROM pg_tables WHERE schemaname='public'")).scalar_one()
    finally:
        owner.dispose()
