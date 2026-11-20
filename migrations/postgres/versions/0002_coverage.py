from alembic import op

revision = '0002_pg_coverage'
down_revision = '0001_pg'
branch_labels = depends_on = None


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql("""CREATE TABLE v1_evaluation_coverage (
        tenant_id VARCHAR NOT NULL REFERENCES v1_tenant(id), run_id VARCHAR NOT NULL,
        run_input_sha256 VARCHAR NOT NULL, format_version BIGINT NOT NULL, evaluation_sha256 VARCHAR NOT NULL,
        canonical_payload BYTEA NOT NULL, payload_sha256 VARCHAR NOT NULL,
        PRIMARY KEY (tenant_id,run_id,run_input_sha256,format_version),
        FOREIGN KEY (tenant_id,run_id) REFERENCES v1_evaluation_run(tenant_id,id) DEFERRABLE INITIALLY DEFERRED)""")
    db.exec_driver_sql('ALTER TABLE v1_evaluation_coverage ENABLE ROW LEVEL SECURITY')
    db.exec_driver_sql('ALTER TABLE v1_evaluation_coverage FORCE ROW LEVEL SECURITY')
    db.exec_driver_sql("""CREATE POLICY tenant_isolation ON v1_evaluation_coverage USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));""")


def downgrade():
    db = op.get_bind()
    db.exec_driver_sql('ALTER TABLE v1_evaluation_coverage NO FORCE ROW LEVEL SECURITY')
    if db.exec_driver_sql('SELECT 1 FROM v1_evaluation_coverage LIMIT 1').first():
        raise RuntimeError('Cannot downgrade populated coverage; use an empty disposable database')
    op.drop_table('v1_evaluation_coverage')
