"""Recovery validates empty ledgers and releases its owned SQLite handles."""
from contextlib import closing
import sqlite3

import pytest

from service import recovery
from tests.v1.helpers import setup


@pytest.mark.parametrize('operation', ['inspect', 'backup', 'restore'])
def test_empty_tenant_invalid_checkpoint_rejected(tmp_path, operation):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source = tmp_path / 'v1.db'
    backup = tmp_path / 'backup.db'
    metadata = recovery.backup_database(source, backup)
    damaged = backup if operation == 'restore' else source
    with closing(sqlite3.connect(damaged)) as db, db:
        db.execute('UPDATE v1_tenant_audit_head SET sequence=7,head_sha256=?', ('f' * 64,))
    metadata['backup_sha256'] = recovery.file_sha256(backup)
    metadata['snapshot']['tenant_heads'][0].update(sequence=7, head_sha256='f' * 64)
    with pytest.raises(ValueError, match='integrity'):
        if operation == 'inspect':
            recovery.inspect_database(source)
        elif operation == 'backup':
            recovery.backup_database(source, tmp_path / 'rejected.db')
        else:
            recovery.restore_database(backup, tmp_path / 'restored.db', metadata)


@pytest.mark.parametrize('operation', ['inspect', 'backup', 'restore'])
@pytest.mark.parametrize('fails', [False, True])
def test_owned_connections_closed_on_success_and_failure(tmp_path, monkeypatch, operation, fails):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source = tmp_path / 'v1.db'
    backup = tmp_path / 'backup.db'
    metadata = recovery.backup_database(source, backup)
    connections = []
    original = sqlite3.connect

    class Connection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

        def backup(self, *args, **kwargs):
            if fails:
                raise RuntimeError('injected backup failure')
            return super().backup(*args, **kwargs)

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=Connection)
        connections.append(connection)
        return connection

    monkeypatch.setattr(recovery.sqlite3, 'connect', connect)
    if fails and operation == 'inspect':
        with closing(original(source)) as db, db:
            db.execute('DROP TABLE v1_actor')
    try:
        if operation == 'inspect':
            recovery.inspect_database(source)
        elif operation == 'backup':
            recovery.backup_database(source, tmp_path / 'copy.db')
        else:
            recovery.restore_database(backup, tmp_path / 'restored.db', metadata)
    except (RuntimeError, ValueError):
        assert fails
    else:
        assert not fails
    try:
        assert connections and all(connection.closed for connection in connections)
        for path in (source, backup):
            moved = path.with_suffix('.moved')
            path.rename(moved)
            moved.unlink()
    finally:
        for connection in connections:
            connection.close()
