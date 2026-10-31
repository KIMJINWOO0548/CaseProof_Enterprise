"""Four real, synthetic local recovery exercises; no external provider or reset API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx

from service.db import make_engine, session_factory
from service.recovery import backup_database, restore_database, inspect_database, utc_now, file_sha256
from service.workspace import ACTORS, ROOT, seed_workspace


def run_drills(output):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='caseproof.local-recovery-drill.v1', started_at=utc_now(),
        scope='LOCAL synthetic SQLite v1; single worker; loopback HTTP; disposable data',
        environment=dict(python=platform.python_version(), os=platform.platform(), sqlite=sqlite3.sqlite_version),
        command='python -m scripts.recovery_drill', exercises=[],
        external_anchor=dict(status='SKIPPED', reason='No independent infrastructure configured', bonus=0),
        external_review=dict(status='SKIPPED', reason='No consented independent reviewer data', bonus=0))
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='caseproof-recovery-', ignore_cleanup_errors=True) as temporary:
            directory = Path(temporary)
            database = directory / 'workspace.db'
            env = dict(os.environ, CASEPROOF_DEMO_MODE='1', CASEPROOF_V1_MIGRATION_MODE='disposable',
                       CASEPROOF_V1_DATABASE_URL='sqlite:///' + database.as_posix())
            with (output / 'server.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
                               env=env, stdout=log, stderr=log, check=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                engine = make_engine(env['CASEPROOF_V1_DATABASE_URL'])
                try:
                    with session_factory(engine).begin() as db:
                        preset = seed_workspace(db)['presets'][0]
                finally:
                    engine.dispose()
                tokens = {name: secrets.token_urlsafe(32) for name in ACTORS}
                registry = {hashlib.sha256(token.encode()).hexdigest(): dict(tenant_id='fictional', actor_id=name)
                            for name, token in tokens.items()}
                profile = directory / 'profile.json'
                profile.write_text(json.dumps(dict(database_path=str(database), tokens=tokens, registry=registry)), encoding='utf-8')
                profile.chmod(0o600)
                with socket.socket() as reservation:
                    reservation.bind(('127.0.0.1', 0))
                    port = reservation.getsockname()[1]
                base = 'http://127.0.0.1:' + str(port)

                def start():
                    return subprocess.Popen([sys.executable, '-u', '-m', 'scripts.windows_checks', 'scripts.v1_demo',
                        '--profile', str(profile), '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=log,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

                def stop():
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        process.terminate()
                    process.wait(timeout=15)

                with httpx.Client(base_url=base, timeout=2, trust_env=False) as client:
                    def headers(actor):
                        return {'Authorization': 'Bearer ' + tokens[actor]}

                    def ready():
                        deadline = time.monotonic() + 120
                        while time.monotonic() < deadline:
                            if process.poll() is not None:
                                raise RuntimeError('Owned server exited before HTTP readiness')
                            try:
                                if client.get('/api/v1/workspace', headers=headers('auditor')).status_code == 200:
                                    return
                            except httpx.TransportError:
                                pass
                            time.sleep(0.05)
                        raise RuntimeError('HTTP readiness deadline exceeded')

                    def start_ready():
                        nonlocal process
                        # Windows can fail before bind with 10014; retry initialization only.
                        for attempt in range(16):
                            process = start()
                            try:
                                ready()
                                report.setdefault('server_initialization_attempts', []).append(attempt + 1)
                                return
                            except RuntimeError:
                                if process.poll() is None:
                                    raise
                        raise RuntimeError('Owned server initialization failed 16 times')

                    def post(suffix, body, revision=None, actor='analyst', expected=200):
                        h = headers(actor) | {'Idempotency-Key': 'recovery_' + uuid4().hex}
                        if revision is not None:
                            h['X-Expected-Revision'] = str(revision)
                        response = client.post('/api/v1/changes' + suffix, json=body, headers=h)
                        if response.status_code != expected:
                            raise AssertionError('Mutation status: ' + str(response.status_code) + ' expected ' + str(expected))
                        return response.json().get('data')

                    def pending():
                        change = post('', preset['create_body'], expected=201)
                        suffix = '/' + change['change_id']
                        post(suffix + '/evaluation-runs', dict(suite_version_id=preset['create_body']['suite_version_id'],
                             case_inputs=preset['case_inputs']), 1, expected=201)
                        post(suffix + '/submit', {}, 2)
                        post(suffix + '/domain-decision', dict(decision='APPROVE', reason='Synthetic domain drill acceptance'), 3, 'reviewer')
                        return suffix

                    start_ready()
                    started = utc_now()
                    clock = time.monotonic()
                    old_pid = process.pid
                    stop()
                    outage_observed = False
                    try:
                        client.get('/api/v1/workspace', headers=headers('auditor'))
                    except httpx.TransportError:
                        outage_observed = True
                    assert outage_observed, 'Stopped process still served HTTP'
                    start_ready()
                    report['exercises'].append(dict(name='service_outage', status='PASS', started_at=started,
                        completed_at=utc_now(), old_pid=old_pid, restarted_pid=process.pid,
                        outage_observed=True, readiness_rto_ms=round((time.monotonic()-clock)*1000),
                        readiness_polling='GET only; application mutations are never retried'))

                    started = utc_now()
                    assert client.get('/api/v1/workspace', headers=headers('analyst')).status_code == 200
                    with sqlite3.connect(database) as db:
                        db.execute("UPDATE v1_actor SET enabled=0 WHERE tenant_id='fictional' AND id='analyst'")
                    before = inspect_database(database)
                    before_bytes = file_sha256(database)
                    response = client.post('/api/v1/changes', json=preset['create_body'], headers=headers('analyst') |
                                           {'Idempotency-Key': 'stolen_' + uuid4().hex})
                    assert response.status_code == 401
                    assert inspect_database(database) == before
                    assert file_sha256(database) == before_bytes
                    assert client.get('/api/v1/workspace', headers=headers('analyst')).status_code == 401
                    report['exercises'].append(dict(name='token_theft', status='PASS', started_at=started,
                        completed_at=utc_now(), before_disable_http=200, after_disable_http=401,
                        unauthorized_mutation_http=401, database_effect=False,
                        containment='Owner disabled demo Actor; registry rotation still required after restore'))
                    with sqlite3.connect(database) as db:
                        db.execute("UPDATE v1_actor SET enabled=1 WHERE tenant_id='fictional' AND id='analyst'")

                    suffix = pending()
                    post(suffix + '/release-decision', dict(decision='APPROVE', reason='Synthetic release drill acceptance'), 4, 'approver')
                    started = utc_now()
                    backup = directory / 'backup.db'
                    metadata = backup_database(database, backup)
                    post('', preset['create_body'], expected=201)
                    committed_at = utc_now()
                    current = inspect_database(database)
                    clock = time.monotonic()
                    restored = directory / 'restored.db'
                    result = restore_database(backup, restored, metadata)
                    rto = round((time.monotonic()-clock)*1000)
                    actual = inspect_database(restored)
                    assert actual == metadata['snapshot'] and actual['envelopes']
                    lost = current['tenant_heads'][0]['sequence'] - actual['tenant_heads'][0]['sequence']
                    assert lost == 1
                    report['exercises'].append(dict(name='rollback_restore', status='PASS', started_at=started,
                        completed_at=utc_now(), backup=metadata, restore=result, restore_rto_ms=rto,
                        observed_rpo_lost_committed_transitions=lost, last_post_backup_commit_observed_at=committed_at,
                        rpo_basis='One observed committed create after backup is absent in restored checkpoint',
                        restored_exposed_to_http=False))

                    suffix = pending()
                    started = utc_now()
                    with sqlite3.connect(database) as db:
                        db.execute('UPDATE v1_change SET revision=3 WHERE id=?', (suffix[1:],))
                    before = file_sha256(database)
                    post(suffix + '/release-decision', dict(decision='APPROVE', reason='Must block tampered synthetic evidence'), 4, 'approver', expected=409)
                    evidence = client.get('/api/v1/changes' + suffix + '/evidence', headers=headers('auditor'))
                    assert evidence.status_code == 200 and evidence.json()['data']['historical_integrity'] == 'INVALID'
                    with sqlite3.connect(database) as db:
                        status, envelope = db.execute('SELECT status,approval_envelope_sha256 FROM v1_change WHERE id=?', (suffix[1:],)).fetchone()
                    assert status == 'PENDING_RELEASE' and envelope is None
                    assert file_sha256(database) == before
                    report['exercises'].append(dict(name='evidence_tampering', status='PASS', started_at=started,
                        completed_at=utc_now(), approval_http=409, historical_integrity='INVALID',
                        release_created=False, mutation='Owner changed latest Change revision projection'))
                    stop()
                    process = None
    except Exception as error:
        report['failure'] = dict(type=type(error).__name__, message=str(error)[:250])
    finally:
        if process is not None and process.poll() is None:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                process.terminate()
            process.wait(timeout=15)
        report['completed_at'] = utc_now()
        report['status'] = 'PASS' if len(report['exercises']) == 4 and 'failure' not in report else 'FAILED'
        report['source_sha256'] = {name: file_sha256(ROOT / name) for name in
            ('service/recovery.py', 'scripts/recovery_drill.py', 'service/workspace.py', 'service/api/v1.py')}
        report['exit_code'] = 0 if report['status'] == 'PASS' else 1
        (output / 'recovery-drill.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / 'reports' / 'runs' / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-recovery-' + uuid4().hex[:8])
    report = run_drills(output)
    print(report['status'] + ': ' + str(output / 'recovery-drill.json'))
    raise SystemExit(report['exit_code'])


if __name__ == '__main__':
    main()
