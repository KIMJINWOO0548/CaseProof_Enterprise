"""Different changes serialize on the same tenant head without losing either run."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select, text

from service import models_v1 as m
from service.auth import tenant_context
from service.commands import execute_command
from service.domain.canonical import content_hash
from service.repositories import decode, load_history
from tests.v1.helpers import command


def test_different_changes_two_physical_sessions_preserve_tenant_chain(pg_factory, pg_engine, pg_seed):
    actors, body = pg_seed
    identities = [execute_command(pg_factory, actors['analyst'], command(body)).data['change_id']
                  for _ in range(2)]
    with pg_factory.begin() as db:
        tenant_context(db, 'tenant-a')
        previous_sequence = db.get(m.TenantAuditHead, 'tenant-a').sequence
    barrier = Barrier(2, timeout=20)

    def worker(identity):
        payload = {'suite_version_id': body['suite_version_id'], 'case_inputs': [
            {'case_id': case, 'claim_days': 30, 'case_context': {}} for case in ('case-a', 'case-b')]}
        with pg_engine.connect() as connection:
            backend = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            connection.rollback()
            db = pg_factory(bind=connection)
            try:
                barrier.wait()
                result = execute_command(lambda: db, actors['analyst'],
                                         command(payload, 'evaluation-runs', identity, 1))
                return backend, result
            finally:
                db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, identity) for identity in identities]
        outcomes = [future.result(timeout=60) for future in futures]
    assert len({backend for backend, _ in outcomes}) == 2
    assert {result.data['change_id'] for _, result in outcomes} == set(identities)
    assert all(result.status_code == 201 and result.result_revision == 2 and not result.replayed
               for _, result in outcomes)
    with pg_factory.begin() as db:
        tenant_context(db, 'tenant-a')
        head = db.get(m.TenantAuditHead, 'tenant-a')
        assert head.sequence == previous_sequence + 2
        events = db.scalars(select(m.AuditEvent).where(m.AuditEvent.sequence > previous_sequence)
                            .order_by(m.AuditEvent.sequence)).all()
        assert [event.sequence for event in events] == [previous_sequence + 1, previous_sequence + 2]
        assert {event.subject_id for event in events} == set(identities)
        assert head.head_sha256 == content_hash('audit-event', decode(events[-1]))
        for identity in identities:
            history = load_history(db, 'tenant-a', identity)
            assert history['snapshot']['revision'] == 2
            assert len(history['runs']) == 1
            assert len(history['snapshots']) == len(history['transitions']) == len(history['events']) == 2
