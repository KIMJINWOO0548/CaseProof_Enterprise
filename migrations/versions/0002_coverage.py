from alembic import op

revision = '0002_coverage'
down_revision = '0001_v1'
branch_labels = depends_on = None


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql("""CREATE TABLE v1_evaluation_coverage (
        tenant_id VARCHAR NOT NULL REFERENCES v1_tenant(id), run_id VARCHAR NOT NULL,
        run_input_sha256 VARCHAR NOT NULL, format_version BIGINT NOT NULL, evaluation_sha256 VARCHAR NOT NULL,
        canonical_payload BLOB NOT NULL, payload_sha256 VARCHAR NOT NULL,
        PRIMARY KEY (tenant_id,run_id,run_input_sha256,format_version),
        FOREIGN KEY (tenant_id,run_id) REFERENCES v1_evaluation_run(tenant_id,id) DEFERRABLE INITIALLY DEFERRED)""")
    for operation in ('UPDATE', 'DELETE'):
        db.exec_driver_sql(f"""CREATE TRIGGER v1_evaluation_coverage_no_{operation.lower()} BEFORE {operation}
            ON v1_evaluation_coverage BEGIN SELECT RAISE(ABORT,'v1 append-only record'); END""")
    db.exec_driver_sql("""CREATE TRIGGER v1_evaluation_coverage_no_replace BEFORE INSERT ON v1_evaluation_coverage
        WHEN EXISTS (SELECT 1 FROM v1_evaluation_coverage WHERE (tenant_id,run_id,run_input_sha256,format_version) =
        (NEW.tenant_id,NEW.run_id,NEW.run_input_sha256,NEW.format_version))
        BEGIN SELECT RAISE(ABORT,'v1 append-only record'); END""")


def downgrade():
    db = op.get_bind()
    if db.exec_driver_sql('SELECT 1 FROM v1_evaluation_coverage LIMIT 1').first():
        raise RuntimeError('Cannot downgrade populated coverage; use an empty disposable database')
    op.drop_table('v1_evaluation_coverage')
