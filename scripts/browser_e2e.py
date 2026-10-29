"""Optional real Chromium E2E with an owned temporary SQLite database.

python -m pip install --require-hashes -r requirements-browser.lock
python -m playwright install chromium
python -m scripts.browser_e2e
No external URLs, existing database deletion, saved tokens, or screenshots.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def main():
    from playwright.sync_api import sync_playwright
    from service.db import make_engine, create_tables, session_factory
    from service.seed import seed_demo

    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='caseproof_browser_') as folder:
        dbfile = Path(folder) / 'demo.sqlite3'
        engine = make_engine(f'sqlite:///{dbfile}')
        try:
            create_tables(engine)
            with session_factory(engine)() as session:
                tokens = seed_demo(session)
                session.commit()
        finally:
            engine.dispose()
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            port = reserved.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        env = dict(os.environ, CASEPROOF_DEMO_MODE='1', CASEPROOF_DATABASE_URL=f'sqlite:///{dbfile}')
        log = (Path(folder) / 'server.log').open('w+', encoding='utf-8')
        proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'service.app:app', '--host', '127.0.0.1',
             '--port', str(port), '--workers', '1'],
            cwd=root, env=env, stdout=log, stderr=log,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError('Temporary local API process exited before readiness')
                try:
                    with urllib.request.urlopen(url + '/api/health', timeout=.5) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(.1)
            else:
                raise TimeoutError('Temporary local API did not become ready in 20 seconds')
            with sync_playwright() as pw:
                options = {'headless': True}
                if os.getenv('CASEPROOF_CHROMIUM_PATH'):
                    options['executable_path'] = os.environ['CASEPROOF_CHROMIUM_PATH']
                browser = pw.chromium.launch(**options)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 940})
                    page_errors = []
                    page.on('pageerror', lambda e: page_errors.append(str(e)))
                    page.on('dialog', lambda d: d.accept('개정 약관의 시점과 근거 검증을 완료했습니다'))
                    page.goto(url, wait_until='domcontentloaded')

                    def login(user):
                        page.locator('#token').fill(tokens[user])
                        page.locator('#connect').click()
                        page.locator('#workspace').wait_for(state='visible')
                        # Authentication with a fresh random token also verifies this is our server.
                        page.wait_for_function("document.querySelector('#scope').options.length > 0")

                    def switch(user):
                        page.locator('#switch').click()
                        page.locator('#login').wait_for(state='visible')
                        login(user)

                    login('aurora-analyst')
                    page.locator('#scope').select_option(label='AUTO-101 · DOCUMENT_WINDOW_DAYS [claim_received_date]')
                    page.locator('#createbtn').click()
                    page.locator('#evalform').wait_for(state='visible')
                    for index, (claim, day) in enumerate([('30', '2026-06-30'), ('20', '2026-07-01')], 1):
                        page.locator('#evalform input[name=claim_days]').fill(claim)
                        page.locator('#evalform input[name=basis_date]').fill(day)
                        page.locator('#evalform button[type=submit]').click()
                        page.wait_for_function('(n) => document.querySelectorAll(".result.pass").length >= n', arg=index)
                    page.locator('#submitbtn').click()
                    page.get_by_text('PENDING_DOMAIN_REVIEW').first.wait_for()
                    switch('aurora-reviewer')
                    page.locator('#list .change').first.click()
                    page.locator('#domainapprove').click()
                    page.get_by_text('PENDING_RELEASE').first.wait_for()
                    switch('aurora-approver')
                    page.locator('#list .change').first.click()
                    page.locator('#releaseapprove').click()
                    page.get_by_text('APPROVED_FOR_DEMO').first.wait_for()
                    page.wait_for_function('() => { try { const e = JSON.parse(document.querySelector("#evidence").innerText); return e.matches_approval === true; } catch { return false; }}')
                    evidence = json.loads(page.locator('#evidence').inner_text())
                    assert evidence['audit_chain_verified'] is True
                    assert evidence['record_integrity_verified'] is True
                    assert evidence['real_release'] is False
                    assert not page_errors, page_errors
                    print('CHROMIUM_E2E_PASS: create -> two evaluations -> domain review -> release -> evidence')
                finally:
                    browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            log.close()


if __name__ == '__main__':
    main()
