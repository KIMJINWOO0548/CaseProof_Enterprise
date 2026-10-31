"""Small request checks always run with Node; optional real browser checks never pass empty.

Set CASEPROOF_V1_BROWSER_URL and CASEPROOF_V1_BROWSER_CREDENTIALS (an ignored
JSON file containing analyst/domain/release tokens) to exercise a running disposable demo.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_v1_request_recovery():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is not installed; request-helper checks were not run')
    result = subprocess.run([node, 'scripts/v1_ui_probe.js'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS: exact replay' in result.stdout


def test_v1_browser_three_person_correction():
    playwright = pytest.importorskip('playwright.sync_api', reason='Optional Playwright is absent; real browser NOT run')
    url = os.environ.get('CASEPROOF_V1_BROWSER_URL')
    credentials = os.environ.get('CASEPROOF_V1_BROWSER_CREDENTIALS')
    if not url or not credentials:
        pytest.skip('Disposable v1 browser URL and ignored credentials file are required')
    tokens = json.loads(Path(credentials).read_text(encoding='utf-8'))
    days = int(os.environ.get('CASEPROOF_V1_BROWSER_PASSING_DAYS', '24'))
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except playwright.Error as error:
            pytest.skip('Optional Chromium unavailable: ' + str(error).splitlines()[0])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def login(token):
            if page.locator('#switch-role').is_visible():
                page.locator('#switch-role').click()
            page.locator('#token').fill(token)
            page.locator('#login-form button').click()
            page.locator('#workspace').wait_for(state='visible')
            page.wait_for_function("document.querySelector('#queue').getAttribute('aria-busy') === 'false'")

        def status(value):
            page.wait_for_function("v => document.querySelector('#change-status')?.textContent === v", arg=value)

        def evaluate():
            page.locator('[data-case-input]').evaluate_all('(els, days) => els.forEach(el => {el.value = days})', days)
            page.locator('#evaluate').click()
            page.wait_for_function("document.querySelector('#run-result')?.textContent.includes('PASS')")

        def decide(value, reason):
            page.locator('[data-decision="' + value + '"]').click()
            page.locator('#reason').fill(reason)
            page.locator('#decision-form button[type=submit]').click()

        page.goto(url.rstrip('/') + '/v1')
        login(tokens['analyst'])
        page.locator('#new-change').click()
        page.keyboard.press('Escape')
        assert page.locator('#new-change').evaluate('el => el === document.activeElement')
        page.locator('#new-change').click()
        page.locator('#preset').select_option(index=2)
        page.locator('#title').fill('<img src=x onerror="window.__xss=1">')
        page.locator('#create-form button[type=submit]').click()
        status('DRAFT')
        original = page.locator('#change-id').text_content()
        evaluate()

        def drop_success(route):
            response = route.fetch()
            assert response.ok
            route.abort()

        page.route('**/api/v1/changes/*/submit', drop_success, times=1)
        page.locator('#submit-change').click()
        page.locator('#retry-request').wait_for(state='visible')
        page.locator('#retry-request').click()
        status('PENDING_DOMAIN_REVIEW')
        login(tokens['domain'])
        page.locator('[data-change-id="' + original + '"]').click()
        decide('REJECT', '<svg onload="window.__xss=1"> correction needed')
        status('REJECTED')
        login(tokens['analyst'])
        page.locator('[data-change-id="' + original + '"]').click()
        page.locator('#correct-change').click()
        page.locator('#create-form button[type=submit]').click()
        status('DRAFT')
        corrected = page.locator('#change-id').text_content()
        assert corrected != original
        assert original in page.locator('#detail').text_content()
        evaluate()
        page.locator('#submit-change').click()
        status('PENDING_DOMAIN_REVIEW')
        login(tokens['domain'])
        page.locator('[data-change-id="' + corrected + '"]').click()
        decide('APPROVE', 'Corrected full suite independently reviewed.')
        status('PENDING_RELEASE')
        login(tokens['release'])
        page.locator('[data-change-id="' + corrected + '"]').click()
        decide('APPROVE', 'Independent release checks completed.')
        status('APPROVED_FOR_DEMO')
        page.locator('#load-evidence').click()
        page.wait_for_function("document.querySelector('#evidence').textContent.includes('VALID')")
        assert page.evaluate('window.__xss') is None
        assert page.evaluate('localStorage.length + sessionStorage.length') == 0
        page.set_viewport_size({'width': 375, 'height': 812})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
        browser.close()
