import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from service.models_v1 import BaseV1, IMMUTABLE_TABLES

TABLES = tuple(BaseV1.metadata.tables)
COMPOSITE_FKS = [(table.name, tuple(column.name for column in fk.columns))
                 for table in BaseV1.metadata.tables.values() for fk in table.foreign_key_constraints
                 if len(fk.columns) > 1]


@pytest.mark.parametrize('table_name,columns', COMPOSITE_FKS)
def test_each_composite_fk_rejects_existing_b_only_reference(pg_owner_engine, pg_engine, pg_populated, table_name, columns):
    from sqlalchemy import create_engine, select, inspect
    from uuid import uuid4
    table = BaseV1.metadata.tables[table_name]
    owner = pg_owner_engine
    try:
        info = next(fk for fk in inspect(owner).get_foreign_keys(table_name) if tuple(fk['constrained_columns']) == columns)
        target = BaseV1.metadata.tables[info['referred_table']]
        with owner.begin() as db:
            db.execute(text("SELECT set_config('app.tenant_id','tenant-b',true)"))
            row = dict(db.execute(select(table)).first()._mapping)
            query = select(target)
            if 'revision' in target.c:
                query = query.order_by(target.c.revision.desc())
            parent = dict(db.execute(query).first()._mapping)
        for local, remote in zip(columns, info['referred_columns']):
            row[local] = parent[remote]
        row['tenant_id'] = 'tenant-a'
        if 'sequence' in row:
            row['sequence'] = 9007199254740000
        for lower, upper in (('input_revision', 'output_revision'), ('revision_from', 'revision_to'), ('preapproval_revision', 'approved_revision')):
            if lower in row and upper in row:
                if upper in columns:
                    row[lower] = row[upper] - 1
                else:
                    row[upper] = row[lower] + 1
        if 'id' in table.c:
            row['id'] = str(uuid4())
        with pg_engine.connect() as db:
            db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
            # Prove the referenced identifier exists in B and has no A counterpart.
            predicate = [target.c[remote] == row[local] for local, remote in zip(columns, info['referred_columns'])]
            assert db.execute(select(target).where(*predicate)).first() is None
            with pytest.raises(DBAPIError) as error:
                db.execute(table.insert().values(**row))
                quoted = db.dialect.identifier_preparer.quote_identifier(info['name'])
                db.exec_driver_sql(f'SET CONSTRAINTS {quoted} IMMEDIATE')
            assert error.value.orig.sqlstate == '23503'
            assert error.value.orig.diag.constraint_name == info['name']
    finally:
        pass


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('context', [None, '', 'bad tenant', 'tenant-a'])
def test_every_table_foreign_tenant_insert_denied(pg_engine, pg_seed, table, context):
    from sqlalchemy import Boolean, LargeBinary, BigInteger
    model = BaseV1.metadata.tables[table]
    row = {}
    for column in model.c:
        name = column.name
        if column.nullable:
            row[name] = None
        elif isinstance(column.type, Boolean):
            row[name] = True
        elif isinstance(column.type, LargeBinary):
            row[name] = b'{}'
        elif isinstance(column.type, BigInteger):
            row[name] = 0 if name == 'revision_from' else 2 if name in ('output_revision', 'approved_revision') else 201 if name == 'original_status' else 1
        else:
            row[name] = '0' * 64 if name.endswith('sha256') else 'DOMAIN' if name == 'stage' else 'DRAFT' if name == 'status' else 'synthetic'
    row['id' if table == 'v1_tenant' else 'tenant_id'] = 'tenant-b'
    with pg_engine.connect() as db:
        if context is not None:
            db.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"), {'tenant': context})
        with pytest.raises(DBAPIError) as error:
            db.execute(model.insert().values(**row))
        assert error.value.orig.sqlstate == '42501'


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('context', [None, '', 'bad tenant', 'tenant-a'])
def test_every_table_scoped_reads(pg_engine, pg_populated, table, context):
    column = 'id' if table == 'v1_tenant' else 'tenant_id'
    with pg_engine.begin() as db:
        if context is not None:
            db.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"), {'tenant': context})
        rows = db.execute(text(f'SELECT DISTINCT {column} FROM "{table}"')).scalars().all()
        assert set(rows) == ({'tenant-a'} if context == 'tenant-a' else set())


@pytest.mark.parametrize('table', TABLES)
def test_every_table_cross_tenant_update_delete(pg_engine, pg_seed, table):
    column = 'id' if table == 'v1_tenant' else 'tenant_id'
    for operation in ('UPDATE', 'DELETE'):
        with pg_engine.connect() as db:
            db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
            allowed = db.execute(text('SELECT has_table_privilege(current_user,:table,:op)'), {'table': table, 'op': operation}).scalar_one()
            statement = (f'UPDATE "{table}" SET {column}={column}' if operation == 'UPDATE' else f'DELETE FROM "{table}"') + f" WHERE {column}='tenant-b'"
            if allowed:
                assert db.execute(text(statement)).rowcount == 0
            else:
                with pytest.raises(DBAPIError) as error:
                    db.execute(text(statement))
                assert error.value.orig.sqlstate == '42501'
            db.rollback()


@pytest.mark.parametrize('context', [None, '', 'bad tenant', 'tenant-a'])
def test_insert_context_and_foreign_tenant_denied(pg_engine, pg_seed, context):
    with pg_engine.connect() as db:
        if context is not None:
            db.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"), {'tenant': context})
        with pytest.raises(DBAPIError) as error:
            db.execute(text("INSERT INTO v1_source_snapshot VALUES ('tenant-b','forbidden','source_v1',:payload,:digest)"), {'payload': b'{}', 'digest': '0' * 64})
        assert error.value.orig.sqlstate == '42501'


def test_cross_tenant_composite_fk_denied(pg_engine, pg_seed):
    with pg_engine.connect() as db:
        db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
        db.execute(text("INSERT INTO v1_source_bundle_member VALUES ('tenant-a','missing-b-bundle','missing-b-source','missing-b-policy')"))
        with pytest.raises(DBAPIError) as error:
            db.commit()
        assert error.value.orig.sqlstate == '23503'


@pytest.mark.parametrize('finish', ['commit', 'rollback', 'exception'])
def test_reused_connection_clears_context(pg_database, pg_seed, finish):
    from sqlalchemy import create_engine
    engine = create_engine(pg_database.app_url, pool_size=1, max_overflow=0)
    try:
        try:
            with engine.connect() as db:
                backend = db.execute(text('SELECT pg_backend_pid()')).scalar_one()
                db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
                assert db.execute(text('SELECT count(*) FROM v1_actor')).scalar_one() == 3
                if finish == 'exception':
                    raise RuntimeError('synthetic exception')
                getattr(db, finish)()
        except RuntimeError:
            assert finish == 'exception'
        with engine.begin() as db:
            assert db.execute(text('SELECT pg_backend_pid()')).scalar_one() == backend
            assert db.execute(text('SELECT count(*) FROM v1_actor')).scalar_one() == 0
            db.execute(text("SELECT set_config('app.tenant_id','tenant-b',true)"))
            assert db.execute(text('SELECT count(*) FROM v1_actor')).scalar_one() == 3
    finally:
        engine.dispose()
