"""Recovery rejects inconsistent request ledgers in disposable synthetic copies."""
from contextlib import closing
import sqlite3
from uuid import uuid4

import pytest

from service.commands import execute_command
from service.db import make_engine, session_factory
from service.domain.canonical import canonical_bytes, content_hash, parse_json
from service.recovery import backup_database, file_sha256, inspect_database, restore_database
from tests.v1.helpers import command, dump, evaluated, setup


def damage_request_ledger(path, fault):
    # Simulate offline corruption only in this test's own temporary database.
    # Restore the original trigger SQL so schema drift cannot explain rejection.
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory = sqlite3.Row
        triggers = db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                              "AND tbl_name='v1_idempotency_record'").fetchall()
        for trigger in triggers:
            db.execute('DROP TRIGGER "' + trigger['name'] + '"')
        records = [dict(row) for row in db.execute(
            'SELECT * FROM v1_idempotency_record ORDER BY result_revision')]
        first = records[0]
        if fault in ('missing', 'compensated'):
            db.execute('DELETE FROM v1_idempotency_record WHERE id=?', (first['id'],))
        if fault in ('duplicate', 'compensated'):
            duplicate = dict(records[1] if fault == 'compensated' else first)
            payload = parse_json(duplicate['canonical_payload'])
            duplicate['id'] = str(uuid4())
            duplicate['key'] = payload['key'] = 'duplicate_' + uuid4().hex
            duplicate['canonical_payload'] = canonical_bytes(payload)
            duplicate['payload_sha256'] = content_hash('idempotency', payload)
            columns = list(duplicate)
            db.execute('INSERT INTO v1_idempotency_record (' + ','.join(columns) + ') VALUES ('
                       + ','.join('?' for _ in columns) + ')', [duplicate[name] for name in columns])
        elif fault == 'payload':
            db.execute('UPDATE v1_idempotency_record SET canonical_payload=? WHERE id=?', (b'{}', first['id']))
        elif fault == 'fingerprint':
            db.execute('UPDATE v1_idempotency_record SET fingerprint_sha256=? WHERE id=?', ('f' * 64, first['id']))
        elif fault == 'status':
            db.execute('UPDATE v1_idempotency_record SET original_status=200 WHERE id=?', (first['id'],))
        elif fault == 'response':
            payload = parse_json(first['canonical_payload'])
            payload['response_data_json']['title'] = 'Altered synthetic historical response'
            db.execute('UPDATE v1_idempotency_record SET canonical_payload=?,payload_sha256=? WHERE id=?',
                       (canonical_bytes(payload), content_hash('idempotency', payload), first['id']))
        for trigger in triggers:
            db.execute(trigger['sql'])
        assert db.execute('PRAGMA integrity_check').fetchall()[0][0] == 'ok'
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('operation', ['inspect', 'backup', 'restore'])
@pytest.mark.parametrize('fault', ['payload', 'fingerprint', 'status', 'response', 'missing', 'duplicate', 'compensated'])
def test_inconsistent_success_request_ledger_is_not_accepted_as_recoverable(tmp_path, operation, fault):
    factory, actors, body = setup(tmp_path)
    evaluated(factory, actors, body)
    factory.kw['bind'].dispose()
    source = tmp_path / 'v1.db'
    backup = tmp_path / 'backup.db'
    metadata = backup_database(source, backup)
    damaged = backup if operation == 'restore' else source
    damage_request_ledger(damaged, fault)
    original = damaged.read_bytes()
    metadata['backup_sha256'] = file_sha256(backup)
    if fault == 'missing':
        metadata['snapshot']['row_counts']['v1_idempotency_record'] -= 1
    elif fault == 'duplicate':
        metadata['snapshot']['row_counts']['v1_idempotency_record'] += 1
    target = tmp_path / 'rejected.db'
    with pytest.raises(ValueError, match='[Ii]dempotency|request ledger'):
        if operation == 'inspect':
            inspect_database(source)
        elif operation == 'backup':
            backup_database(source, target)
        else:
            restore_database(backup, target, metadata)
    assert damaged.read_bytes() == original
    if operation == 'restore':
        assert not target.exists()


@pytest.mark.parametrize('final_decision', ['APPROVE', 'DOMAIN_REJECT', 'RELEASE_REJECT'])
def test_restored_multiple_change_histories_replay_their_original_committed_results(tmp_path, final_decision):
    factory, actors, body = setup(tmp_path)
    requests = []

    def execute(actor, request):
        result = execute_command(factory, actor, request)
        requests.append((actor, request, result))
        return result

    identity = execute(actors['analyst'], command(body)).data['change_id']
    execute(actors['analyst'], command({'suite_version_id': body['suite_version_id'],
        'case_inputs': [{'case_id': case, 'claim_days': 30, 'case_context': {}} for case in ('case-a', 'case-b')]},
        'evaluation-runs', identity, 1))
    execute(actors['analyst'], command({}, 'submit', identity, 2))
    execute(actors['reviewer'], command({'decision': 'REJECT' if final_decision == 'DOMAIN_REJECT' else 'APPROVE',
                                      'reason': 'Synthetic domain review'},
                                      'domain-decision', identity, 3))
    if final_decision != 'DOMAIN_REJECT':
        execute(actors['approver'], command({'decision': 'REJECT' if final_decision == 'RELEASE_REJECT' else 'APPROVE',
                                          'reason': 'Synthetic release review'},
                                          'release-decision', identity, 4))
    execute(actors['analyst'], command(dict(body, title='Second synthetic change')))
    factory.kw['bind'].dispose()
    backup = tmp_path / 'backup.db'
    metadata = backup_database(tmp_path / 'v1.db', backup)
    target = tmp_path / 'restored.db'
    restore_database(backup, target, metadata)
    engine = make_engine('sqlite:///' + target.as_posix())
    restored = session_factory(engine)
    try:
        before = dump(restored)
        for actor, request, original in requests:
            replayed = execute_command(restored, actor, request)
            assert replayed.replayed
            assert (replayed.status_code, replayed.result_revision, replayed.data) == (
                original.status_code, original.result_revision, original.data)
        assert dump(restored) == before
        assert inspect_database(target) == metadata['snapshot']
    finally:
        engine.dispose()
