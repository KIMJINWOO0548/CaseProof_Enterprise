"""Optional keyboard acceptance against the disposable v1 launcher and real SQLite."""
import os

import pytest

from scripts.v1_demo import _listener
from service import models_v1 as m
from tests.browser.test_reconnect_workflow import _launch
from tests.v1.test_workspace import workspace, headers, mutate


def test_coverage_keyboard_and_revocation(workspace, tmp_path):
    if os.environ.get('CASEPROOF_V1_RECONNECT_BROWSER') != '1':
        pytest.skip('Opt-in local Chromium acceptance')
    pw = pytest.importorskip('playwright.sync_api')
    client, factory, registry = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    mutate(client, '/' + change['change_id'] + '/evaluation-runs',
           {'suite_version_id': change['suite_version_id'], 'case_inputs': preset['case_inputs']}, 1)
    with _listener(0, 128) as listener:
        port = listener.getsockname()[1]
    with _launch(tmp_path / 'profile.json', tmp_path / 'workspace.db', registry, port) as base, pw.sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(channel='chrome')
        try:
            page = browser.new_page()
            page.goto(base + '/v1')
            page.locator('#token').fill('test-analyst')
            page.locator('#login-form button').click()
            page.locator('#queue button[data-change-id]').click()
            page.locator('#load-run-history').click()
            page.locator('#read-coverage').focus()
            page.keyboard.press('Enter')
            page.locator('#coverage-filter').select_option('executed')
            page.locator('#coverage-filter').focus()
            page.keyboard.press('Tab')
            page.keyboard.press('Enter')
            page.keyboard.press('Tab')
            page.keyboard.press('Enter')
            pw.expect(page.locator('#run-history details[open]')).to_have_count(2)
            with factory.begin() as db:
                db.get(m.Actor, ('fictional', 'analyst')).enabled = False
            page.locator('#read-coverage').click()
            pw.expect(page.locator('#coverage-filter')).to_have_count(0)
            pw.expect(page.locator('#run-history')).not_to_contain_text('harbor-base')
        finally:
            browser.close()
