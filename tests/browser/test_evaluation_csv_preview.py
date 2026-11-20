"""Optional Chromium acceptance for the disposable workspace CSV path."""
import csv
import io
import json
import os

import pytest

from scripts.v1_demo import _listener
from tests.browser.test_reconnect_workflow import _launch
from tests.v1.test_workspace import headers, mutate, workspace


def test_csv_preview_keyboard_and_original_evaluation(workspace, tmp_path):
    if os.environ.get('CASEPROOF_V1_RECONNECT_BROWSER') != '1':
        pytest.skip('Opt-in local Chromium acceptance')
    pw = pytest.importorskip('playwright.sync_api')
    client, _, registry = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    identity = change['change_id']
    path = f'/api/v1/changes/{identity}/evaluation-runs'
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(('case_id', 'claim_days', 'case_context'))
    for case in preset['case_inputs']:
        writer.writerow((case['case_id'], case['claim_days'], json.dumps(case['case_context'])))
    good = buffer.getvalue().encode()
    bad = good.replace(b',12,', b',12.5,')
    assert good != bad

    with _listener(0, 128) as listener:
        port = listener.getsockname()[1]
    with _launch(tmp_path / 'profile.json', tmp_path / 'workspace.db', registry, port) as base, pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel='chrome')
        try:
            page = browser.new_page()
            page.goto(base + '/v1')
            page.locator('#token').fill('test-analyst')
            page.locator('#login-form button').click()
            page.locator(f'#queue button[data-change-id="{identity}"]').click()
            file = page.locator('#case-csv')
            check = page.locator('#preview-case-csv')
            evaluate = page.locator('#evaluate-case-csv')
            file.set_input_files({'name': 'synthetic.csv', 'mimeType': 'text/csv', 'buffer': bad})
            check.focus()
            page.keyboard.press('Enter')
            pw.expect(page.locator('#case-csv-result')).to_contain_text('2행 · claim_days · INVALID_INTEGER')
            pw.expect(evaluate).to_be_disabled()
            file.set_input_files({'name': 'synthetic.csv', 'mimeType': 'text/csv', 'buffer': good})
            check.focus()
            page.keyboard.press('Enter')
            pw.expect(evaluate).to_be_enabled()
            assert client.get(path, headers=headers()).json()['data']['total_runs'] == 0

            def lose_evaluation_response(route):
                if route.request.method == 'POST':
                    assert route.fetch().status == 201
                    route.abort()
                else:
                    route.continue_()

            page.route(base + path, lose_evaluation_response)
            evaluate.focus()
            page.keyboard.press('Enter')
            retry = page.locator('#retry-request')
            pw.expect(retry).to_be_enabled()
            retry.focus()
            page.keyboard.press('Enter')
            pw.expect(page.locator('#run-result')).to_contain_text('COMPLETE')
            assert client.get(path, headers=headers()).json()['data']['total_runs'] == 1
        finally:
            browser.close()
