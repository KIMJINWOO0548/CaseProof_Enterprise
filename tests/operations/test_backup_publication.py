"""Failed backups must not publish unusable files or block a safe retry."""
from contextlib import closing
import sqlite3
import pytest
from service import recovery
from tests.v1.helpers import setup


def test_missing_source_does_not_reserve_target(tmp_path):
    target = tmp_path / 'backup.db'
    with pytest.raises(sqlite3.OperationalError):
        recovery.backup_database(tmp_path / 'missing.db', target)
    assert not target.exists()
    assert not list(tmp_path.glob('.caseproof-backup-*'))


def test_invalid_backup_does_not_publish_and_can_retry(tmp_path):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source, target = tmp_path / 'v1.db', tmp_path / 'backup.db'
    with closing(sqlite3.connect(source)) as db, db:
        db.execute('UPDATE v1_tenant_audit_head SET sequence=7')
    with pytest.raises(ValueError, match='integrity'):
        recovery.backup_database(source, target)
    assert not target.exists()
    assert not list(tmp_path.glob('.caseproof-backup-*'))
    with closing(sqlite3.connect(source)) as db, db:
        db.execute('UPDATE v1_tenant_audit_head SET sequence=0')
    metadata = recovery.backup_database(source, target)
    assert metadata['backup_sha256'] == recovery.file_sha256(target)
    assert recovery.inspect_database(target) == metadata['snapshot']


def test_target_not_visible_during_validation_and_raced_file_preserved(tmp_path, monkeypatch):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    target = tmp_path / 'backup.db'
    inspect = recovery.inspect_database
    def race(path):
        assert not target.exists()
        result = inspect(path)
        target.write_bytes(b'concurrent winner')
        return result
    monkeypatch.setattr(recovery, 'inspect_database', race)
    with pytest.raises(FileExistsError):
        recovery.backup_database(tmp_path / 'v1.db', target)
    assert target.read_bytes() == b'concurrent winner'
    assert not list(tmp_path.glob('.caseproof-backup-*'))

@pytest.mark.parametrize('failure', ['before', 'after'])
def test_publish_error_preserves_any_published_valid_backup(tmp_path, monkeypatch, failure):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    target = tmp_path / 'backup.db'
    publish_name = 'rename' if recovery.os.name == 'nt' else 'link'
    publish = getattr(recovery.os, publish_name)
    def fail(source, destination):
        if failure == 'after':
            publish(source, destination)
        raise OSError('injected publication failure')
    monkeypatch.setattr(recovery.os, publish_name, fail)
    with pytest.raises(OSError, match='injected'):
        recovery.backup_database(tmp_path / 'v1.db', target)
    assert not list(tmp_path.glob('.caseproof-backup-*'))
    if failure == 'after':
        assert recovery.inspect_database(target)['integrity_check'] == 'ok'
        before = target.read_bytes()
        with pytest.raises(FileExistsError):
            recovery.backup_database(tmp_path / 'v1.db', target)
        assert target.read_bytes() == before
    else:
        assert not target.exists()
