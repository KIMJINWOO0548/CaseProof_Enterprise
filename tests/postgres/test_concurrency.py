"""Two physical PostgreSQL sessions; no SQLite/thread substitute."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text
from service.commands import execute_command
from service.auth import tenant_context
from service.repositories import load_history
from tests.v1.helpers import command


@pytest.mark.parametrize('trial', range(100))
def test_same_key_two_independent_sessions_one_effect(pg_factory, pg_engine, pg_seed, trial):
    actors, body = pg_seed
    request = command(body, key=f'pg_trial_{trial:03d}_same_key')
    barrier = Barrier(2, timeout=20)

    def worker():
        # Keep the physical connection checked out across the barrier and command.
        with pg_engine.connect() as connection:
            backend = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            connection.rollback()
            db = pg_factory(bind=connection)
            barrier.wait()
            try:
                result = execute_command(lambda: db, actors['analyst'], request)
                return backend, result
            finally:
                db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        outcomes = [future.result(timeout=60) for future in futures]
    assert len({backend for backend, _ in outcomes}) == 2
    results = [result for _, result in outcomes]
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].data == results[1].data
    assert [result.result_revision for result in results] == [1, 1]
    with pg_factory.begin() as db:
        tenant_context(db, 'tenant-a')
        history = load_history(db, 'tenant-a', results[0].data['change_id'])
        assert len(history['snapshots']) == len(history['transitions']) == len(history['events']) == 1
        assert db.execute(text('SELECT count(*) FROM v1_idempotency_record WHERE key=:key'), {'key': request.key}).scalar_one() == 1
        assert db.execute(text('SELECT count(*)=count(DISTINCT sequence) FROM v1_audit_event')).scalar_one()
