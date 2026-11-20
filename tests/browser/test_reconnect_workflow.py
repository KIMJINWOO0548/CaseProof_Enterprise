"""Opt-in browser test of the documented launcher with isolated SQLite data."""

from contextlib import closing, contextmanager
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time

from alembic import command
from alembic.config import Config
import httpx
import pytest

from scripts.v1_demo import _listener
from service.db import make_engine, session_factory
from service.recovery import backup_database, file_sha256, reactivate_reviewed_actors, restore_database
from service.workspace import ACTORS, ROOT, seed_workspace


def _registry(tokens):
    return {hashlib.sha256(token.encode()).hexdigest(): {'tenant_id': 'fictional', 'actor_id': actor}
            for actor, token in tokens.items()}


@contextmanager
def _launch(profile, database, registry, port):
    profile.write_text(json.dumps({'database_path': str(database), 'registry': registry}), encoding='utf-8')
    log_path = profile.with_suffix('.log')
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-u', '-m', 'scripts.windows_checks', 'scripts.v1_demo',
             '--profile', str(profile), '--port', str(port)], cwd=ROOT, stdout=log, stderr=log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        try:
            base = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 30
            with httpx.Client(base_url=base, timeout=1, trust_env=False) as probe:
                while time.monotonic() < deadline:
                    assert process.poll() is None, log_path.read_text(encoding='utf-8')
                    try:
                        assert probe.get('/v1').status_code == 200
                    except httpx.TransportError:
                        time.sleep(0.05)
                        continue
                    break
                else:
                    pytest.fail('v1 launcher never reached HTTP readiness')
            yield base
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def _query(database, statement, *params):
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        return db.execute(statement, params).fetchall()


def _request_parts(request):
    return {name: request.header_value(name) for name in ('idempotency-key', 'x-expected-revision',
            'x-caseproof-request-context')} | {'path': request.url.split('/api/v1/', 1)[1],
                                                'body': request.post_data}


def _receipt_evidence(database, change_id, evidence):
    expected_revisions = [(1, 'DRAFT'), (2, 'DRAFT'), (3, 'PENDING_DOMAIN_REVIEW'),
                          (4, 'PENDING_RELEASE'), (5, 'APPROVED_FOR_DEMO')]
    revisions = _query(database, 'SELECT revision, canonical_payload FROM v1_change_revision WHERE change_id=? ORDER BY revision', change_id)
    assert [(revision, json.loads(raw)['status']) for revision, raw in revisions] == expected_revisions
    transitions = _query(database, 'SELECT revision_from, revision_to, actor_id FROM v1_change_transition WHERE change_id=? ORDER BY revision_to', change_id)
    assert transitions == [(0, 1, 'analyst'), (1, 2, 'analyst'), (2, 3, 'analyst'),
                           (3, 4, 'reviewer'), (4, 5, 'approver')]
    notes = _query(database, 'SELECT stage, actor_id, canonical_payload FROM v1_decision_note WHERE change_id=? ORDER BY input_revision', change_id)
    assert [(stage, actor, json.loads(raw)['reason']) for stage, actor, raw in notes] == [
        ('DOMAIN', 'reviewer', 'Synthetic domain review accepted'),
        ('RELEASE', 'approver', 'Synthetic final approval accepted'),
    ]
    assert _query(database, 'SELECT result_revision FROM v1_idempotency_record WHERE change_id=? ORDER BY result_revision',
                  change_id) == [(revision,) for revision, _ in expected_revisions]
    assert evidence['approved_revision'] == 5 and evidence['historical_integrity'] == 'VALID'
    assert evidence['external_anchor'] == 'NOT_CONFIGURED'
    refs = evidence['immutable_refs']
    for purpose, reference in [('approval-envelope', 'approval_envelope_ref'),
                               ('evaluation-run', 'run_refs'), ('source', 'source_refs')]:
        ref = refs[reference] if reference == 'approval_envelope_ref' else refs[reference][0]
        if reference == 'approval_envelope_ref':
            rows = _query(database, 'SELECT canonical_payload FROM v1_approval_envelope WHERE change_id=?', change_id)
        elif reference == 'run_refs':
            rows = _query(database, 'SELECT canonical_payload FROM v1_evaluation_run WHERE id=? AND change_id=?', ref['id'], change_id)
        else:
            rows = _query(database, 'SELECT canonical_payload FROM v1_source_snapshot WHERE id=?', ref['id'])
        [(raw,)] = rows
        digest = hashlib.sha256(f'caseproof:{purpose}:v1\n'.encode('ascii') + raw).hexdigest()
        assert ref['payload_sha256'] == digest
        if reference == 'approval_envelope_ref':
            assert evidence['envelope_sha256'] == digest
        elif reference == 'run_refs':
            run = json.loads(raw)
            assert run['schema'] == 'evaluation_run_v2'
            assert (run['completion'], run['gate_summary']) == ('COMPLETE', 'PASS')
            assert run['suite_version_id'] == refs['suite_ref']['id']
            assert run['case_results'][0]['case_id'] == 'lantern-base'
            assert run['case_results'][0]['verdict'] == 'PASS'
        else:
            source = json.loads(raw)
            assert (source['source_id'], source['policy_version_id'], source['value']) == ('lantern-source', 'v1', 24)


def test_native_reconnect_restart_revocation_and_older_restore(tmp_path, monkeypatch):
    if os.environ.get('CASEPROOF_V1_RECONNECT_BROWSER') != '1':
        pytest.skip('Set CASEPROOF_V1_RECONNECT_BROWSER=1 to run against real Chromium and loopback SQLite')
    playwright = pytest.importorskip('playwright.sync_api', reason='Optional Playwright unavailable')
    database, backup, restored = (tmp_path / name for name in ('source.db', 'older.db', 'restored.db'))
    url = 'sqlite:///' + database.as_posix()
    monkeypatch.setenv('CASEPROOF_DEMO_MODE', '1')
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', url)
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    engine = make_engine(url)
    try:
        with session_factory(engine).begin() as db:
            seed_workspace(db)
    finally:
        engine.dispose()
    tokens = {actor: secrets.token_urlsafe(32) for actor in ACTORS}
    registry = _registry(tokens)
    with _listener(0, 128) as listener:
        port = listener.getsockname()[1]
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        print('Chromium', browser.version)
        context = browser.new_context()
        page_errors = []

        def new_page(base):
            page = context.new_page()
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            page.goto(base + '/v1')
            return page

        def login(page, actor, token=None, status=200):
            if page.locator('#switch-role').is_visible():
                page.locator('#switch-role').click()
            page.locator('#token').fill(tokens[actor] if token is None else token)
            with page.expect_response('**/api/v1/workspace') as pending:
                page.locator('#login-form button').click()
            response = pending.value
            assert response.status == status
            if status == 200:
                playwright.expect(page.locator('#actor')).to_contain_text('fictional / ' + actor)
                playwright.expect(page.locator('#queue')).to_have_attribute('aria-busy', 'false')
                return response.json()['data']['request_context']
            playwright.expect(page.locator('#login')).to_be_visible()
            playwright.expect(page.locator('#message')).to_contain_text('UNAUTHENTICATED')

        def select_change(page, change_id):
            page.locator(f'[data-change-id="{change_id}"]').click()
            playwright.expect(page.locator('#change-id')).to_have_text(change_id)

        def stage(page, status, revision):
            playwright.expect(page.locator('#change-status')).to_have_text(status)
            playwright.expect(page.locator('.change-meta p')).to_have_text(f'Revision {revision}')

        def open_create(page, title):
            page.locator('#new-change').click()
            page.locator('#preset').select_option(index=2)
            page.locator('#title').fill(title)

        def create_and_evaluate(page, title):
            open_create(page, title)
            page.locator('#create-form button[type=submit]').click()
            stage(page, 'DRAFT', 1)
            change_id = page.locator('#change-id').text_content()
            page.locator('[data-case-input]').fill('24')
            page.locator('#evaluate').click()
            stage(page, 'DRAFT', 2)
            playwright.expect(page.locator('#run-result')).to_contain_text('COMPLETE · PASS')
            playwright.expect(page.locator('#run-result')).to_contain_text('lantern-base')
            return change_id

        def open_decision(page, reason):
            page.locator('#decision-APPROVE').click()
            page.locator('#reason').fill(reason)

        def inspect_pending(page, captured, known_tokens):
            snapshot = context.storage_state()
            assert not snapshot['cookies']
            assert not any(token in json.dumps(snapshot) for token in known_tokens)
            entries = [entry for origin in snapshot['origins'] for entry in origin['localStorage']]
            assert len(entries) == 1 and entries[0]['name'].endswith('["fictional","analyst"]')
            intent = json.loads(entries[0]['value'])
            assert set(intent) == {'version', 'context', 'path', 'body', 'revision', 'key'}
            assert intent['key'] == captured['idempotency-key']
            assert intent['body'] == captured['body']
            assert intent['context'] == captured['x-caseproof-request-context']
            assert intent['path'] == '/api/v1/' + captured['path']
            assert intent['revision'] == (int(captured['x-expected-revision']) if captured['x-expected-revision'] else None)
            assert page.evaluate('sessionStorage.length') == 0

        def committed_then_dropped(page, path, button, status):
            captured = {}

            def intercept(route):
                assert route.request.method == 'POST'
                captured['request'] = _request_parts(route.request)
                inspect_pending(page, captured['request'], tokens.values())
                response = route.fetch(max_retries=0)
                captured['status'] = response.status
                captured['reply'] = response.json()
                route.abort()

            page.route(path, intercept, times=1)
            page.locator(button).click()
            playwright.expect(page.locator('#message')).to_contain_text('처리 결과 미확정')
            playwright.expect(page.locator('#retry-request')).to_be_enabled()
            assert captured['status'] == status and captured['reply']['replayed'] is False
            inspect_pending(page, captured['request'], tokens.values())
            return captured

        with _launch(tmp_path / 'initial.json', database, registry, port) as base:
            page = new_page(base)
            initial_context = login(page, 'analyst')
            synthetic_rows = [dict(change_id=f'00000000-0000-4000-8000-{n:012d}',
                title=f'Synthetic pagination {n}', pack_version_id='synthetic', revision=1, status='DRAFT')
                for n in range(201)]
            fail_continuation = False

            def paged_list(route):
                second = '?after=' in route.request.url
                if second and fail_continuation:
                    route.abort()
                else:
                    route.fulfill(json={'data': synthetic_rows[200:] if second else synthetic_rows[:200],
                        'pagination': {'limit': 200, 'next_cursor': None if second else synthetic_rows[199]['change_id']}})

            page.route('**/api/v1/changes', paged_list)
            page.route('**/api/v1/changes?after=*', paged_list)
            page.locator('#refresh').click()
            playwright.expect(page.locator('#queue button[data-change-id]')).to_have_count(201)
            fail_continuation = True
            page.locator('#refresh').click()
            playwright.expect(page.locator('#queue')).to_contain_text('목록을 불러오지 못했습니다')
            playwright.expect(page.locator('#queue button[data-change-id]')).to_have_count(0)
            page.unroute('**/api/v1/changes', paged_list)
            page.unroute('**/api/v1/changes?after=*', paged_list)
            page.locator('#refresh').click()
            playwright.expect(page.locator('#queue')).to_have_attribute('aria-busy', 'false')
            print('Actual Chromium rendered 201 synthetic paged rows; second-page disconnect displayed failure, never partial success.')
            change_id = create_and_evaluate(page, 'Synthetic reconnect approval')
            submit_path = f'**/api/v1/changes/{change_id}/submit'
            dropped = committed_then_dropped(page, submit_path, '#submit-change', 200)
            assert dropped['reply']['result_revision'] == 3
            assert dropped['reply']['data']['status'] == 'PENDING_DOMAIN_REVIEW'
            assert dropped['request']['x-expected-revision'] == '2'
            assert dropped['request']['x-caseproof-request-context'] == initial_context
            playwright.expect(page.locator('#change-status')).to_have_count(0)
            page.close()

        with _launch(tmp_path / 'restart.json', database, registry, port) as base:
            page = new_page(base)
            login(page, 'reviewer')
            playwright.expect(page.locator('#recovery')).to_be_hidden()
            assert login(page, 'analyst') == initial_context
            playwright.expect(page.locator('#pending-key')).to_have_text(dropped['request']['idempotency-key'])
            playwright.expect(page.locator('#new-change')).to_be_disabled()
            with page.expect_response('**/api/v1/mutations/' + dropped['request']['idempotency-key']) as pending:
                page.locator('#retry-request').click()
            replay = pending.value
            assert replay.status == 200 and replay.request.method == 'GET'
            assert replay.json() == dropped['reply'] | {'replayed': True, 'original_status': 200}
            stage(page, 'PENDING_DOMAIN_REVIEW', 3)
            playwright.expect(page.locator('#message')).to_contain_text('현재 상태를 확인했습니다')
            playwright.expect(page.locator('#recovery')).to_be_hidden()
            assert _query(database, 'SELECT count(*) FROM v1_idempotency_record') == [(3,)]
            print('Committed submit lost, tab closed and server restarted. Same request result recovered by GET without repost.')

            login(page, 'reviewer')
            select_change(page, change_id)
            open_decision(page, 'Synthetic domain review accepted')
            page.locator('#decision-form button[type=submit]').click()
            stage(page, 'PENDING_RELEASE', 4)
            login(page, 'approver')
            select_change(page, change_id)
            open_decision(page, 'Synthetic final approval accepted')
            page.locator('#decision-form button[type=submit]').click()
            stage(page, 'APPROVED_FOR_DEMO', 5)
            with page.expect_response(f'**/api/v1/changes/{change_id}/evidence') as pending:
                page.locator('#load-evidence').click()
            evidence = pending.value.json()['data']
            playwright.expect(page.locator('#evidence')).to_contain_text('VALID')
            _receipt_evidence(database, change_id, evidence)
            page.screenshot(path=tmp_path / 'verified-approval.png')

            login(page, 'analyst')
            waiting = create_and_evaluate(page, 'Synthetic reviewer revocation')
            page.locator('#submit-change').click()
            stage(page, 'PENDING_DOMAIN_REVIEW', 3)
            older = backup_database(database, backup)
            login(page, 'reviewer')
            select_change(page, waiting)
            open_decision(page, 'Revoked reviewer cannot approve')
            with closing(sqlite3.connect(database)) as db, db:
                assert db.execute('UPDATE v1_actor SET roles_payload=? WHERE tenant_id=? AND id=?',
                                  (b'["AUDITOR"]', 'fictional', 'reviewer')).rowcount == 1
            with page.expect_response(f'**/api/v1/changes/{waiting}/domain-decision') as pending:
                page.locator('#decision-form button[type=submit]').click()
            assert pending.value.status == 403
            playwright.expect(page.locator('#message')).to_contain_text('FORBIDDEN')
            playwright.expect(page.locator('#change-status')).to_have_count(0)
            assert _query(database, 'SELECT status, revision FROM v1_change WHERE id=?', waiting) == [('PENDING_DOMAIN_REVIEW', 3)]
            assert _query(database, 'SELECT count(*) FROM v1_decision_note WHERE change_id=?', waiting) == [(0,)]
            print('Reviewer role revoked after opening decision dialog. HTTP 403 and zero decision records.')

            login(page, 'analyst')
            open_create(page, 'Post-backup uncertain synthetic change')
            after_backup = committed_then_dropped(page, '**/api/v1/changes', '#create-form button[type=submit]', 201)
            absent = after_backup['reply']['data']['change_id']
            assert _query(database, 'SELECT count(*) FROM v1_change WHERE id=?', absent) == [(1,)]
            page.close()

        restore_database(backup, restored, older)
        assert _query(restored, 'SELECT count(*) FROM v1_actor WHERE enabled') == [(0,)]
        assert _query(restored, 'SELECT count(*) FROM v1_change WHERE id=?', absent) == [(0,)]
        # Operator review reapplies the current audited role and rotates all approved credentials.
        rotated = {actor: secrets.token_urlsafe(32) for actor in ('analyst', 'reviewer')}
        next_registry = _registry(rotated)
        reactivate_reviewed_actors(restored, file_sha256(restored), [
            {'tenant_id': 'fictional', 'actor_id': 'analyst', 'roles': ['ANALYST']},
            {'tenant_id': 'fictional', 'actor_id': 'reviewer', 'roles': ['AUDITOR']},
        ], registry, next_registry, 'browser-synthetic-rotation')

        with _launch(tmp_path / 'restore.json', restored, next_registry, port) as base:
            page = new_page(base)
            restored_posts = []

            def count_post(request):
                if request.method == 'POST':
                    restored_posts.append(request.method)

            page.on('request', count_post)
            login(page, 'reviewer', status=401)
            login(page, 'reviewer', token=rotated['reviewer'])
            playwright.expect(page.locator('#actor')).to_have_text('fictional / reviewer · AUDITOR')
            select_change(page, waiting)
            stage(page, 'PENDING_DOMAIN_REVIEW', 3)
            playwright.expect(page.locator('#decision-APPROVE')).to_have_count(0)
            assert login(page, 'analyst', token=rotated['analyst']) != initial_context
            inspect_pending(page, after_backup['request'], (*tokens.values(), *rotated.values()))
            playwright.expect(page.locator('#recovery-message')).to_contain_text('복원본')
            playwright.expect(page.locator('#retry-request')).to_be_disabled()
            playwright.expect(page.locator('#new-change')).to_be_disabled()
            select_change(page, change_id)
            stage(page, 'APPROVED_FOR_DEMO', 5)
            with page.expect_response(f'**/api/v1/changes/{change_id}/evidence') as pending:
                page.locator('#load-evidence').click()
            restored_evidence = pending.value.json()['data']
            playwright.expect(page.locator('#evidence')).to_contain_text('VALID')
            assert restored_evidence == evidence
            _receipt_evidence(restored, change_id, restored_evidence)
            assert _query(restored, 'SELECT count(*) FROM v1_change') == [(2,)]
            assert _query(restored, 'SELECT count(*) FROM v1_idempotency_record') == [(8,)]
            assert restored_posts == []
            page.screenshot(path=tmp_path / 'restored-retry-blocked.png')
            assert not page_errors
            print('Stale restore at same origin: old token rejected, rotated role remains AUDITOR, pending retry blocked, '
                  'two changes/eight effects retained and original approval/run/source hashes match.')
        browser.close()
