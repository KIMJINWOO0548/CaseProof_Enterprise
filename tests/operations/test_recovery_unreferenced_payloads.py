"""Unreferenced snapshots are future execution inputs, not unchecked backup data."""
from contextlib import closing
import sqlite3
import pytest
from service import recovery
from tests.v1.helpers import setup


@pytest.mark.parametrize('table', ['source_snapshot', 'policy_snapshot', 'candidate_snapshot',
    'source_bundle', 'dataset_snapshot', 'suite_snapshot', 'evaluator_snapshot', 'adapter_snapshot'])
@pytest.mark.parametrize('operation', ['inspect', 'backup', 'restore'])
def test_unreferenced_payload_corruption_rejected(tmp_path, table, operation):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    source, backup, target = (tmp_path / name for name in ('v1.db', 'backup.db', 'target.db'))
    metadata = recovery.backup_database(source, backup)
    damaged = backup if operation == 'restore' else source
    name = 'v1_' + table
    with closing(sqlite3.connect(damaged)) as db, db:
        triggers = db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (name,)).fetchall()
        for trigger, _ in triggers:
            db.execute('DROP TRIGGER "' + trigger + '"')
        db.execute('UPDATE "' + name + '" SET canonical_payload=?', (b'{}',))
        for _, sql in triggers:
            db.execute(sql)
        assert db.execute('SELECT count(*) FROM v1_change').fetchone()[0] == 0
        assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    original = damaged.read_bytes()
    metadata['backup_sha256'] = recovery.file_sha256(backup)
    with pytest.raises(ValueError, match='integrity'):
        if operation == 'inspect':
            recovery.inspect_database(source)
        elif operation == 'backup':
            recovery.backup_database(source, target)
        else:
            recovery.restore_database(backup, target, metadata)
    assert damaged.read_bytes() == original
    assert not target.exists()
