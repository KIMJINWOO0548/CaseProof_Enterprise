"""Dedicated PostgreSQL migration entry point: injected disposable owner connection only."""
from alembic import context
from sqlalchemy import inspect, text
from scripts.pg_test_bootstrap import validate_database_name

config = context.config
connection = config.attributes.get('connection')
if context.is_offline_mode() or connection is None:
    raise RuntimeError('Use scripts.pg_test_bootstrap with an explicit disposable owner connection')
if connection.dialect.name != 'postgresql':
    raise RuntimeError('PostgreSQL required; SQLite is not a substitute')
validate_database_name(connection.exec_driver_sql('SELECT current_database()').scalar_one())
version = int(connection.exec_driver_sql('SHOW server_version_num').scalar_one())
if not 170000 <= version < 180000:
    raise RuntimeError('This disposable migration requires PostgreSQL 17')
owner = connection.execute(text("SELECT pg_get_userbyid(datdba) = current_user FROM pg_database WHERE datname = current_database()" )).scalar_one()
if not owner:
    raise RuntimeError('Migration connection must own the disposable database')
existing = set(inspect(connection).get_table_names())
if existing and 'caseproof_pg_alembic_version' not in existing:
    raise RuntimeError('Refusing an existing unversioned database')
if any(not name.startswith('v1_') and name != 'caseproof_pg_alembic_version' for name in existing):
    raise RuntimeError('Refusing non-v1 tables')
context.configure(connection=connection, version_table='caseproof_pg_alembic_version')
with context.begin_transaction():
    context.run_migrations()
