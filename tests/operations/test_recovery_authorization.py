import pytest
from sqlalchemy import update
from service import models_v1 as m
from service.api.errors import DomainError
from service.commands import execute_command
from service.db import make_engine, session_factory
from service.recovery import backup_database, restore_database
from tests.v1.helpers import setup, command, dump


def test_stale_backup_restores_all_actors_quarantined(tmp_path):
    factory, actors, body = setup(tmp_path)
    request = command(body)
    execute_command(factory, actors['analyst'], request)
    backup = tmp_path / 'backup.db'
    metadata = backup_database(tmp_path / 'v1.db', backup)
    with factory.begin() as db:
        db.execute(update(m.Actor).values(enabled=False))
    factory.kw['bind'].dispose()
    original = backup.read_bytes()
    target = tmp_path / 'restored.db'
    report = restore_database(backup, target, metadata)
    engine = make_engine('sqlite:///' + target.as_posix())
    restored = session_factory(engine)
    try:
        with restored() as db:
            from sqlalchemy import select
            assert not any(actor.enabled for actor in db.execute(select(m.Actor)).scalars())
        before = dump(restored)
        for pending in (request, command(body)):
            with pytest.raises(DomainError, match='UNAUTHENTICATED'):
                execute_command(restored, actors['analyst'], pending)
        assert dump(restored) == before
        assert report['authorization_state'] == 'QUARANTINED'
        assert backup.read_bytes() == original
    finally:
        engine.dispose()

def test_restore_preserves_frozen_approval_and_current_withdrawal(tmp_path):
    from uuid import uuid4
    from service.repositories import add_payload, load_history
    from service.domain.evidence import verify_evidence
    from tests.v1.test_evidence import approved
    factory, _, _, original = approved(tmp_path)
    with factory.begin() as db:
        add_payload(db, m.SourceEligibilitySnapshot, dict(
            original['refs']['source_eligibility'][0], id=str(uuid4()), sequence=2, eligible=False))
    factory.kw['bind'].dispose()
    backup, target = tmp_path / 'backup.db', tmp_path / 'restored.db'
    metadata = backup_database(tmp_path / 'v1.db', backup)
    restore_database(backup, target, metadata)
    engine = make_engine('sqlite:///' + target.as_posix())
    try:
        with session_factory(engine)() as db:
            actual = load_history(db, 'tenant-a', original['snapshot']['change_id'])
        assert actual['assessment'] == original['assessment']
        assert actual['envelope'] == original['envelope']
        assert actual['refs']['sources'] == original['refs']['sources']
        status = verify_evidence(actual)
        assert status['historical_integrity'] == 'VALID'
        assert status['current_approval_eligibility'] == 'BLOCKED'
        assert status['envelope_sha256'] == verify_evidence(original)['envelope_sha256']
    finally:
        engine.dispose()

@pytest.mark.parametrize('failure', ['quarantine', 'verification', 'publication_race'])
def test_failed_restore_never_publishes_active_database(tmp_path, monkeypatch, failure):
    import sqlite3
    from service import recovery
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    backup, target = tmp_path / 'backup.db', tmp_path / 'restored.db'
    metadata = backup_database(tmp_path / 'v1.db', backup)
    original_connect, original_inspect = sqlite3.connect, recovery.inspect_database
    class BrokenQuarantine(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == 'UPDATE v1_actor SET enabled=0':
                raise sqlite3.OperationalError('injected quarantine failure')
            return super().execute(sql, *args, **kwargs)
    def connect(path, *args, **kwargs):
        if failure == 'quarantine' and '.caseproof-restore-' in str(path):
            kwargs['factory'] = BrokenQuarantine
        return original_connect(path, *args, **kwargs)
    def inspect(path):
        result = original_inspect(path)
        if '.caseproof-restore-' in str(path):
            if failure == 'verification':
                raise ValueError('injected verification failure')
            if failure == 'publication_race':
                target.write_bytes(b'concurrent-owner')
        return result
    monkeypatch.setattr(recovery.sqlite3, 'connect', connect)
    monkeypatch.setattr(recovery, 'inspect_database', inspect)
    with pytest.raises((sqlite3.OperationalError, ValueError, FileExistsError)):
        restore_database(backup, target, metadata)
    if failure == 'publication_race':
        assert target.read_bytes() == b'concurrent-owner'
    else:
        assert not target.exists()
    assert not list(tmp_path.glob('.caseproof-restore-*'))
