import sqlite3

import pytest

from service.recovery import backup_database, restore_database, inspect_database
from tests.v1.helpers import setup, pending_release, command
from service.commands import execute_command


def test_wal_backup_restore_and_checkpoint(tmp_path):
    factory, actors, body = setup(tmp_path)
    identity = pending_release(factory, actors, body)
    execute_command(factory, actors['approver'], command(
        {'decision': 'APPROVE', 'reason': 'Synthetic release accepted'}, 'release-decision', identity, 4))
    source = tmp_path / 'v1.db'
    with sqlite3.connect(source) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute("UPDATE v1_actor SET enabled=0 WHERE id='analyst'")
        db.commit()
        metadata = backup_database(source, tmp_path / 'backup.db')
    assert metadata['snapshot']['tenant_heads'][0]['sequence'] == 5
    assert metadata['snapshot']['envelopes'][0]['sha256']
    restored = tmp_path / 'restored.db'
    restore_database(tmp_path / 'backup.db', restored, metadata)
    assert inspect_database(restored) == metadata['snapshot']
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT enabled FROM v1_actor WHERE id='analyst'").fetchone() == (0,)


def test_corruption_and_existing_files_are_preserved(tmp_path):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source = tmp_path / 'v1.db'
    backup = tmp_path / 'backup.db'
    metadata = backup_database(source, backup)
    existing = tmp_path / 'existing.db'
    existing.write_bytes(b'keep me')
    with pytest.raises(FileExistsError):
        restore_database(backup, existing, metadata)
    assert existing.read_bytes() == b'keep me'
    original = backup.read_bytes()
    with pytest.raises(FileExistsError):
        backup_database(source, backup)
    assert backup.read_bytes() == original
    backup.write_bytes(original[:-64])
    target = tmp_path / 'new.db'
    with pytest.raises(ValueError, match='digest'):
        restore_database(backup, target, metadata)
    assert not target.exists()


def test_wrong_schema_and_invalid_projection_rejected(tmp_path):
    bad = tmp_path / 'bad.db'
    with sqlite3.connect(bad) as db:
        db.execute('CREATE TABLE unrelated (id INTEGER)')
    with pytest.raises(ValueError, match='schema'):
        backup_database(bad, tmp_path / 'no.db')
    factory, actors, body = setup(tmp_path)
    pending_release(factory, actors, body)
    with sqlite3.connect(tmp_path / 'v1.db') as db:
        db.execute('UPDATE v1_change SET revision=1')
    with pytest.raises(ValueError, match='integrity'):
        backup_database(tmp_path / 'v1.db', tmp_path / 'invalid.db')
