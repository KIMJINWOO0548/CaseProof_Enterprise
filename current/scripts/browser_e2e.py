"""Real Chromium UI integration smoke, local synthetic data only.
Run with python scripts/browser_e2e.py (uses system Chromium via Playwright).
"""
from __future__ import annotations
import os, subprocess, sys, tempfile, time, urllib.request, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SCREEN=ROOT/'evidence'
SCREEN.mkdir(exist_ok=True)
DBFILE=SCREEN/'_temporary_ui_demo.sqlite3'
if DBFILE.exists():DBFILE.unlink()
os.environ['CASEPROOF_DEMO_MODE']='1'
from service.db import make_engine,create_tables,session_factory
from service.seed import seed_demo
engine=make_engine(f'sqlite:///{DBFILE}')
create_tables(engine)
with session_factory(engine)() as s:
    toks=seed_demo(s)
    s.commit()
engine.dispose()
PORT=8767
env=dict(os.environ,CASEPROOF_DEMO_MODE='1',CASEPROOF_DATABASE_URL=f'sqlite:///{DBFILE}')
proc=subprocess.Popen([sys.executable,'-m','uvicorn','service.app:app','--host','127.0.0.1','--port',str(PORT),'--workers','1'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
try:
    for i in range(80):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/health',timeout=1) as res:
                if res.status==200:break
        except Exception:time.sleep(.15)
    else:raise RuntimeError('local service did not start: '+(proc.stderr.read()[:2000] if proc.poll() is not None else 'timeout'))
    with sync_playwright() as pw:
        chromium_path=os.getenv('CASEPROOF_CHROMIUM_PATH') or None
        opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
        if chromium_path:opts['executable_path']=chromium_path
        browser=pw.chromium.launch(**opts)
        context=browser.new_context(viewport={'width':1440,'height':940},device_scale_factor=1)
        page=context.new_page()
        page.on('dialog',lambda dialog:dialog.accept('개정 약관의 시점과 근거 검증을 완료했습니다'))
        page.goto(f'http://127.0.0.1:{PORT}/',wait_until='networkidle')
        def login(user):
            page.locator('#token').fill(toks[user]);page.locator('#connect').click()
            page.locator('#workspace').wait_for(state='visible')
            page.wait_for_timeout(150)
        def switch(user):
            page.locator('#switch').click()
            page.locator('#login').wait_for(state='visible')
            login(user)
        login('aurora-analyst')
        page.locator('#scope').select_option(label='AUTO-101 · DOCUMENT_WINDOW_DAYS [claim_received_date]')
        page.locator('#createbtn').click()
        page.locator('#evalform').wait_for(state='visible')
        page.locator('#evalform input[name=claim_days]').fill('30')
        page.locator('#evalform input[name=basis_date]').fill('2026-06-30')
        page.locator('#evalform button[type=submit]').click()
        page.get_by_text('NUMERIC_POLICY_MATCH').wait_for()
        page.screenshot(path=str(SCREEN/'v5_검증_작업화면.png'),full_page=True)
        page.locator('#evalform input[name=claim_days]').fill('20')
        page.locator('#evalform input[name=basis_date]').fill('2026-07-01')
        page.locator('#evalform button[type=submit]').click()
        page.wait_for_function('document.querySelectorAll(".result.pass").length>=2')
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
        page.wait_for_timeout(200)
        page.screenshot(path=str(SCREEN/'v5_승인완료_대시보드.png'),full_page=True)
        evidence=json.loads(page.locator('#evidence').inner_text())
        assert evidence['matches_approval'] is True
        assert evidence['audit_chain_verified'] is True
        assert evidence['real_release'] is False
        print('CHROMIUM_E2E_PASS: login → create → 2 version evaluations → submit → domain review → release approval → evidence verify')
        browser.close()
finally:
    proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill()
    if DBFILE.exists():DBFILE.unlink()
