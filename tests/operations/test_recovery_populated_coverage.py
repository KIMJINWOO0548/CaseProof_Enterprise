"""A migrated SQLite database with real saved coverage remains recoverable."""
from contextlib import closing
import sqlite3
from service.recovery import backup_database, restore_database
from tests.v1.test_workspace import workspace, headers, mutate


def test_migrated_populated_coverage_survives_verified_backup_and_restore(workspace, tmp_path):
    client, _, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    run = mutate(client, '/' + change['change_id'] + '/evaluation-runs',
                 {'suite_version_id': change['suite_version_id'], 'case_inputs': preset['case_inputs']}, 1)['run']
    def rows(path):
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            return db.execute('SELECT tenant_id,run_id,run_input_sha256,format_version,evaluation_sha256,canonical_payload,payload_sha256 FROM v1_evaluation_coverage ORDER BY tenant_id,run_id').fetchall()
    source, backup, restored = [tmp_path / n for n in ('workspace.db', 'verified.bak', 'restored.db')]
    before = rows(source)
    assert len(before) == 1 and before[0][1] == run['id'] and before[0][5] and before[0][6]
    receipt = backup_database(source, backup)
    assert receipt['snapshot']['row_counts']['v1_evaluation_coverage'] == 1
    outcome = restore_database(backup, restored, receipt)
    assert outcome['authorization_state'] == 'QUARANTINED'
    assert rows(source) == rows(backup) == rows(restored) == before
