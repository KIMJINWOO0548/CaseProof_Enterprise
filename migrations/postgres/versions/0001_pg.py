"""Frozen v1 PostgreSQL schema and tenant policies."""
from pathlib import Path
from alembic import op
from sqlalchemy import inspect

revision = '0001_pg'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    ddl = Path(__file__).with_name('0001_schema.sql').read_text(encoding='utf-8')
    for statement in ddl.split(';'):
        if statement.strip():
            op.get_bind().exec_driver_sql(statement)


def downgrade():
    connection = op.get_bind()
    tables = sorted(name for name in inspect(connection).get_table_names() if name.startswith('v1_'))
    # Owner sees all tenants only for the emptiness check; any refusal rolls this DDL back.
    for name in tables:
        connection.exec_driver_sql(f'ALTER TABLE "{name}" NO FORCE ROW LEVEL SECURITY')
    if any(connection.exec_driver_sql(f'SELECT EXISTS (SELECT 1 FROM "{name}")').scalar_one() for name in tables):
        raise RuntimeError('Downgrade is allowed only for an empty disposable database')
    for name in tables:
        connection.exec_driver_sql(f'DROP TABLE "{name}" CASCADE')
