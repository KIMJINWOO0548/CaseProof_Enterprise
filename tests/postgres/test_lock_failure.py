from sqlalchemy import text
from service.api.errors import DomainError
from service.auth import tenant_context
from service.commands import execute_command
from tests.v1.helpers import command
import pytest


def test_actual_deadlock_victim_rollback_and_executor_http_mapping(pg_engine, pg_factory, pg_seed, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from sqlalchemy.exc import DBAPIError
    from service.api.v1 import build_router
    from fastapi import FastAPI
    from tests.v1.test_http import request
    barrier = Barrier(2, timeout=10)
    identities = [str(uuid4()), str(uuid4())]
    lock_base = int(uuid4().hex[:10], 16)

    def worker(index):
        with pg_engine.connect() as db:
            try:
                db.execute(text("SELECT set_config('app.tenant_id','tenant-a',true)"))
                db.execute(text("SET LOCAL statement_timeout='8s'"))
                backend = db.execute(text('SELECT pg_backend_pid()')).scalar_one()
                db.execute(text("INSERT INTO v1_source_snapshot VALUES ('tenant-a',:id,'source_v1',:payload,:digest)"), {'id': identities[index], 'payload': b'{}', 'digest': '0' * 64})
                db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_base + index})
                barrier.wait()
                db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_base + 1 - index})
                db.commit()
                return backend, index, None
            except DBAPIError as error:
                db.rollback()
                return backend, index, error

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert len({backend for backend, _, _ in outcomes}) == 2
    failures = [(index, error) for _, index, error in outcomes if error is not None]
    assert len(failures) == 1
    victim, actual_error = failures[0]
    assert actual_error.orig.sqlstate == '40P01'
    with pg_factory.begin() as db:
        tenant_context(db, 'tenant-a')
        persisted = set(db.execute(text('SELECT id FROM v1_source_snapshot WHERE id IN (:a,:b)'), {'a': identities[0], 'b': identities[1]}).scalars())
        assert identities[victim] not in persisted
        assert persisted == {identities[1 - victim]}

    # Feed the captured genuine DB error through the executor's mapping separately.
    class FailedSession:
        def __enter__(self):
            raise actual_error
        def __exit__(self, *_):
            return False
    actors, body = pg_seed
    with pytest.raises(DomainError) as mapped:
        execute_command(FailedSession, actors['analyst'], command(body))
    assert mapped.value.code == 'RETRYABLE_CONFLICT'
    app = FastAPI()
    app.include_router(build_router(pg_factory, lambda token, db: actors['analyst']))
    def raise_mapped(*args, **kwargs):
        raise mapped.value
    monkeypatch.setattr('service.api.v1.execute_command', raise_mapped)
    response = request(app, 'POST', '/api/v1/changes', body)
    assert response.status_code == 503 and response.headers['Retry-After'] == '1'
    assert response.json()['error']['code'] == 'RETRYABLE_CONFLICT'


def test_tenant_lock_timeout_rolls_back_without_reserving_key(pg_factory, pg_seed):
    actors, body = pg_seed
    request = command(body)
    def snapshot():
        from service.models_v1 import BaseV1
        from sqlalchemy import select
        with pg_factory.begin() as db:
            tenant_context(db, 'tenant-a')
            return {table.name: sorted([tuple(row) for row in db.execute(select(table))], key=repr)
                    for table in BaseV1.metadata.tables.values()}
    before = snapshot()
    with pg_factory.begin() as blocker:
        tenant_context(blocker, 'tenant-a')
        blocker.execute(text('SELECT * FROM v1_tenant_audit_head FOR UPDATE'))
        with pg_factory() as contender:
            contender.execute(text("SET lock_timeout='100ms'"))
            contender.commit()
            try:
                with pytest.raises(DomainError) as error:
                    execute_command(lambda: contender, actors['analyst'], request)
                assert error.value.code == 'RETRYABLE_CONFLICT'
            finally:
                # SET is session-scoped; reset before returning this connection to the pool.
                contender.execute(text('RESET lock_timeout'))
                contender.commit()
    assert snapshot() == before
    with pg_factory.begin() as db:
        tenant_context(db, 'tenant-a')
        assert db.execute(text('SELECT count(*) FROM v1_idempotency_record WHERE key=:key'), {'key': request.key}).scalar_one() == 0
    assert execute_command(pg_factory, actors['analyst'], request).result_revision == 1
