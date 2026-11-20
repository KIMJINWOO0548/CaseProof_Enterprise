"""Opt-in actual Chromium -> loopback API -> persisted 201-row acceptance."""
import os
from uuid import uuid4

import httpx
import pytest

from service import models_v1 as m
from scripts.v1_demo import _listener
from tests.browser.test_reconnect_workflow import _launch
from tests.v1.test_workspace import workspace


def test_real_database_pagination_and_live_revocation(workspace, tmp_path):
    if os.environ.get('CASEPROOF_V1_RECONNECT_BROWSER') != '1':
        pytest.skip('Requires explicit disposable Chromium acceptance')
    pw = pytest.importorskip('playwright.sync_api')
    _, factory, registry = workspace
    database = tmp_path / 'workspace.db'
    with _listener(0, 128) as listener:
        port = listener.getsockname()[1]
    with _launch(tmp_path / 'real-profile.json', database, registry, port) as base:
        headers = {'Authorization': 'Bearer test-analyst'}
        with httpx.Client(base_url=base, trust_env=False, timeout=30) as client:
            assert client.get('/api/v1/changes').status_code == 401
            preset = client.get('/api/v1/workspace', headers=headers).json()['data']['presets'][0]
            expected = []
            for n in range(201):
                response = client.post('/api/v1/changes',
                    headers=headers | {'Idempotency-Key': 'real_' + uuid4().hex},
                    json=dict(preset['create_body'], title=f'Synthetic real pagination {n}'))
                assert response.status_code == 201, response.text
                expected.append(response.json()['data']['change_id'])
            with pw.sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                pages, errors = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                def record(response):
                    if '/api/v1/changes' in response.url:
                        assert response.status == 200
                        pages.append((response.url, response.json()))
                page.on('response', record)
                page.goto(base + '/v1')
                page.locator('#token').fill('test-analyst')
                page.locator('#login-form button').click()
                pw.expect(page.locator('#workspace')).to_be_visible()
                print('Login diagnostics', errors, page.locator('#message').text_content())
                pw.expect(page.locator('#queue')).to_have_attribute('aria-busy', 'false', timeout=90000)
                pw.expect(page.locator('#queue button[data-change-id]')).to_have_count(201)
                actual = page.locator('#queue button[data-change-id]').evaluate_all(
                    '(els) => els.map(el => el.dataset.changeId)')
                assert sorted(actual) == sorted(expected) and len(set(actual)) == 201
                assert len(pages) == 2
                assert [len(body['data']) for _, body in pages] == [200, 1]
                cursor = pages[0][1]['pagination']['next_cursor']
                assert cursor and pages[1][0].endswith('?after=' + cursor)
                assert pages[1][1]['pagination']['next_cursor'] is None
                page.screenshot(path=str(tmp_path / 'real-201.png'), full_page=True)
                page.remove_listener('response', record)
                with factory.begin() as db:
                    db.get(m.Actor, ('fictional', 'analyst')).enabled = False
                with page.expect_response('**/api/v1/changes') as pending:
                    page.locator('#refresh').click()
                assert pending.value.status == 401
                pw.expect(page.locator('#queue button[data-change-id]')).to_have_count(0)
                assert not errors
                print(f'Chromium {browser.version}: real API persisted 201 rows; UI fetched 200 + 1, exact IDs, no mocks; revoked actor HTTP 401 and queue cleared.')
                browser.close()


def test_queue_keeps_newer_authorization_failure_after_older_success(workspace, tmp_path):
    if os.environ.get('CASEPROOF_V1_RECONNECT_BROWSER') != '1':
        pytest.skip('Requires explicit disposable Chromium acceptance')
    pw = pytest.importorskip('playwright.sync_api')
    _, factory, registry = workspace
    with _listener(0, 128) as listener:
        port = listener.getsockname()[1]
    with _launch(tmp_path / 'queue-profile.json', tmp_path / 'workspace.db', registry, port) as base:
        with httpx.Client(base_url=base, trust_env=False, timeout=30,
                          headers={'Authorization': 'Bearer test-analyst'}) as client:
            preset = client.get('/api/v1/workspace').json()['data']['presets'][0]
            result = client.post('/api/v1/changes', headers={'Idempotency-Key': 'queue_' + uuid4().hex},
                                 json=dict(preset['create_body'], title='Synthetic delayed queue'))
            assert result.status_code == 201
        with pw.sync_playwright() as playwright, playwright.chromium.launch() as browser:
            page = browser.new_page()
            page.goto(base + '/v1')
            page.locator('#token').fill('test-analyst')
            page.locator('#login-form button').click()
            queue = page.locator('#queue')
            pw.expect(queue.locator('button[data-change-id]')).to_have_count(1)

            delayed = []

            def delay_first(route):
                if delayed:
                    route.continue_()
                else:
                    response = route.fetch()
                    assert response.ok
                    delayed.append((route, response))

            page.route('**/api/v1/changes', delay_first)
            with page.expect_request('**/api/v1/changes'):
                page.locator('#refresh').click()
            page.locator('#search').fill('Synthetic')
            during_refresh = queue.locator('button[data-change-id]').count()
            with factory.begin() as db:
                db.get(m.Actor, ('fictional', 'analyst')).enabled = False
            with page.expect_response(lambda response: response.url.endswith('/api/v1/changes')
                                      and response.status == 401):
                page.locator('#refresh').click()
            error_text = '목록을 불러오지 못했습니다. 새로고침하세요.'
            pw.expect(queue).to_have_text(error_text)
            page.locator('#search').fill('delayed')
            after_filter = queue.inner_text()

            route, old_response = delayed[0]
            with page.expect_response(lambda response: response.url.endswith('/api/v1/changes')
                                      and response.status == 200):
                route.fulfill(response=old_response)
            page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            assert during_refresh == 0, 'Filtering during refresh restored cached data'
            assert after_filter == error_text, 'Filtering replaced the authorization error with an empty result'
            pw.expect(queue).to_have_text(error_text)
            pw.expect(queue.locator('button[data-change-id]')).to_have_count(0)
