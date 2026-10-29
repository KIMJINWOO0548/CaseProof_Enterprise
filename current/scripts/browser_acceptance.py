"""Optional browser acceptance check: run on a machine where localhost browser access works.

Requires `pip install playwright` and `python -m playwright install chromium`.
Never put production tokens in CLI args. Use CASEPROOF_TEST_ANALYST_TOKEN env var.
This is synthetic demo only, and must be run against a disposable local DB.
"""
from __future__ import annotations
import os, argparse
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='http://127.0.0.1:8000')
    p.add_argument('--output',default='reports/browser_acceptance.png')
    args=p.parse_args()
    token=os.getenv('CASEPROOF_TEST_ANALYST_TOKEN','')
    if not token:raise SystemExit('Set CASEPROOF_TEST_ANALYST_TOKEN using the freshly seeded synthetic demo token')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit('pip install playwright && python -m playwright install chromium') from exc
    with sync_playwright() as pl:
        browser=pl.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':950})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url,wait_until='domcontentloaded',timeout=15000)
        page.locator('#token').fill(token)
        page.locator('#connect').click()
        page.locator('#workspace').wait_for(state='visible')
        assert 'ANALYST' in page.locator('#roles').inner_text()
        # Does not create a persistent change; interactive state checked after login.
        assert page.locator('#createbtn').is_enabled()
        Path(args.output).parent.mkdir(exist_ok=True,parents=True)
        page.screenshot(path=args.output,full_page=True)
        assert not errors, errors
        browser.close()
        print('BROWSER_ACCEPTANCE_PASS (synthetic local demo; interactive browser logged in)')

if __name__=='__main__':main()
