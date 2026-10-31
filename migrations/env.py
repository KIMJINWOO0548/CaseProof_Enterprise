"""Explicit, disposable-only v1 migration entry point; never baseline startup."""
import os
from alembic import context
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from service.models_v1 import BaseV1

config = context.config
target_metadata = BaseV1.metadata
VERSION_TABLE = 'caseproof_v1_alembic_version'

if context.is_offline_mode():
    raise RuntimeError('v1 migrations require an inspected disposable SQLite connection')
if os.environ.get('CASEPROOF_V1_MIGRATION_MODE') != 'disposable':
    raise RuntimeError('CASEPROOF_V1_MIGRATION_MODE=disposable is required')
url = os.environ.get('CASEPROOF_V1_DATABASE_URL')
if not url or make_url(url).get_backend_name() != 'sqlite':
    raise RuntimeError('Explicit CASEPROOF_V1_DATABASE_URL must be SQLite; PostgreSQL awaits G2')
engine = create_engine(url)
try:
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        if connection.exec_driver_sql('PRAGMA foreign_keys').scalar() != 1:
            raise RuntimeError('SQLite foreign keys must be enabled')
        existing = set(inspect(connection).get_table_names())
        expected = set(target_metadata.tables) | {VERSION_TABLE}
        # Refuse before Alembic creates even its version table.
        if existing - expected or (existing and VERSION_TABLE not in existing):
            raise RuntimeError('Refusing existing baseline/non-v1/unversioned schema; legacy-unverified only')
        if inspect(connection).get_view_names():
            raise RuntimeError('Refusing existing views in disposable v1 database')
        connection.commit()
        # sqlite3 legacy mode does not BEGIN for DDL; make rollback real.
        connection.exec_driver_sql('BEGIN')
        context.configure(connection=connection, target_metadata=target_metadata,
                          version_table=VERSION_TABLE, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
finally:
    engine.dispose()
