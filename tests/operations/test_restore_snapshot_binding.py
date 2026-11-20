"""Restore binds all reads to the bytes named by backup metadata."""
from contextlib import closing
import sqlite3
import shutil
from pathlib import Path
import pytest
from service import recovery
from tests.v1.helpers import setup


def role(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT roles_payload FROM v1_actor WHERE id='analyst'").fetchone()[0]


@pytest.mark.parametrize('change_kind', ['update', 'replace'])
def test_backup_change_after_inspection_does_not_change_restored_bytes(tmp_path, monkeypatch, change_kind):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    backup, target = tmp_path / 'backup.db', tmp_path / 'restored.db'
    metadata = recovery.backup_database(tmp_path / 'v1.db', backup)
    expected = role(backup)
    inspect = recovery.inspect_database
    calls = 0
    inspected = []
    def change_after_inspection(path):
        nonlocal calls
        result = inspect(path)
        inspected.append(path)
        calls += 1
        if calls == 1:
            changed = backup
            if change_kind == 'replace':
                changed = tmp_path / 'replacement.db'
                shutil.copyfile(backup, changed)
            with closing(sqlite3.connect(changed)) as db, db:
                db.execute("UPDATE v1_actor SET roles_payload=? WHERE id='analyst'", (b'["AUDITOR"]',))
            if change_kind == 'replace':
                changed.replace(backup)
        return result
    monkeypatch.setattr(recovery, 'inspect_database', change_after_inspection)
    recovery.restore_database(backup, target, metadata)
    assert role(target) == expected
    assert all(not path.parent.exists() for path in inspected)
    assert not list(tmp_path.glob('.caseproof-restore-*'))


def test_wal_changes_not_in_approved_backup_digest_are_not_restored(tmp_path):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source, backup, target = (tmp_path / n for n in ('v1.db', 'backup.db', 'restored.db'))
    with closing(sqlite3.connect(source)) as db:
        db.execute('PRAGMA journal_mode=WAL')
    metadata = recovery.backup_database(source, backup)
    expected = role(backup)
    with closing(sqlite3.connect(backup)) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute("UPDATE v1_actor SET roles_payload=? WHERE id='analyst'", (b'["AUDITOR"]',))
        writer.commit()
        assert recovery.file_sha256(backup) == metadata['backup_sha256']
        recovery.restore_database(backup, target, metadata)
        assert role(target) == expected
        with closing(sqlite3.connect(target)) as check:
            assert check.execute('SELECT count(*) FROM v1_actor WHERE enabled=1').fetchone()[0] == 0
            assert check.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    assert not list(tmp_path.glob('.caseproof-restore-*'))

@pytest.mark.parametrize('failure', ['partial_copy', 'changed_bytes'])
def test_failed_private_snapshot_never_publishes_or_changes_source(tmp_path, monkeypatch, failure):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    backup, target = tmp_path / 'backup.db', tmp_path / 'restored.db'
    metadata = recovery.backup_database(tmp_path / 'v1.db', backup)
    original = backup.read_bytes()
    copy = recovery.shutil.copyfileobj
    copied_to = []
    def fault(source, destination):
        copied_to.append(Path(destination.name))
        if failure == 'partial_copy':
            destination.write(source.read(100))
            raise OSError('injected copy interruption')
        copy(source, destination)
        destination.seek(100)
        destination.write(b'changed')
    monkeypatch.setattr(recovery.shutil, 'copyfileobj', fault)
    with pytest.raises((OSError, ValueError)):
        recovery.restore_database(backup, target, metadata)
    assert backup.read_bytes() == original
    assert copied_to and all(not path.parent.exists() for path in copied_to)
    assert not target.exists()
    assert not list(tmp_path.glob('.caseproof-restore-*'))
