"""Synthetic end-to-end integration smoke, isolated temp SQLite. No real PII or insurance data."""
import argparse, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

os.environ['CASEPROOF_DEMO_MODE'] = '1'
from fastapi.testclient import TestClient
from service.app import create_app
from service.db import create_tables
from service.seed import seed_demo

TOKENS = {name: 'smoke_only_' + name for name in (
    'aurora-analyst', 'aurora-reviewer', 'aurora-approver', 'aurora-auditor',
    'horizon-analyst', 'horizon-reviewer', 'horizon-approver')}

def head(who):
    return {'Authorization':'Bearer '+TOKENS[who]}

def api(client,method,path,who,**kwargs):
    resp=client.request(method,path,headers={**head(who),**kwargs.pop('headers',{})},**kwargs)
    if resp.status_code >=400:
        raise RuntimeError(f'{method} {path}: {resp.status_code} {resp.text}')
    return resp.json()

def run(output: str | Path | None = None):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:8]
    target = Path(output) if output is not None else Path('reports')/'runs'/run_id/'integration_smoke.json'
    if target.exists():
        raise FileExistsError(f'Refusing to overwrite smoke evidence: {target}')
    report={'profile':'SYNTHETIC_DEMO_ONLY','real_llm':False,'real_insurance_decisions':False,
            'recorded_at':datetime.now(timezone.utc).isoformat(),'checks':[]}
    def check(name, condition):
        if not condition:raise AssertionError(name)
        report['checks'].append({'id':name,'passed':True})
    with tempfile.TemporaryDirectory(prefix='caseproof_smoke_') as folder:
        app=create_app('sqlite:///'+str(Path(folder)/'demo.sqlite3'),demo_mode=True)
        create_tables(app.state.db_engine)
        with app.state.session_factory() as db:
            seed_demo(db,TOKENS)
            db.commit()
        with TestClient(app) as client:
            scopes=api(client,'GET','/api/scopes','aurora-analyst')
            scope=next(x for x in scopes if x['rule_key']=='DOCUMENT_WINDOW_DAYS')
            change=api(client,'POST','/api/changes','aurora-analyst',json={
                'title':'자동 연속검증 스모크 (합성 사례)','product':scope['product'],
                'workflow':scope['workflow'],'rule_key':scope['rule_key'],
                'dataset_hash':scope['dataset_hash'],'evaluator_hash':scope['evaluator_hash'],
                'source_hash':scope['source_hash']})
            cid=change['id'];check('change_created', change['status']=='DRAFT')
            foreign=client.get('/api/changes/'+cid,headers=head('horizon-analyst'))
            check('cross_tenant_404',foreign.status_code==404)
            for basis,claim in [('2026-06-30',30),('2026-07-01',20)]:
                result=api(client,'POST',f'/api/changes/{cid}/evaluations','aurora-analyst',
                           headers={'X-Expected-Revision':str(change['revision']),
                                    'Idempotency-Key':'smoketest-'+uuid4().hex},
                           json={'claim_days':claim,'basis_date':basis,'rider_codes':[],
                                 'as_of_recorded':'2026-10-28T00:00:00+09:00'})
                check('evaluation_'+basis,result['verdict']=='PASS')
                change=api(client,'GET','/api/changes/'+cid,'aurora-analyst')
            change=api(client,'POST',f'/api/changes/{cid}/submit','aurora-analyst',
                       json={'expected_revision':change['revision']})
            check('domain_review_pending',change['status']=='PENDING_DOMAIN_REVIEW')
            rejected=client.post(f'/api/changes/{cid}/domain-decision',
                headers=head('aurora-analyst'),json={'expected_revision':change['revision'],
                'decision':'APPROVE','reason':'내가 자기 승인 시도합니다'})
            check('self_approval_denied',rejected.status_code==403)
            change=api(client,'POST',f'/api/changes/{cid}/domain-decision','aurora-reviewer',
                       json={'expected_revision':change['revision'],'decision':'APPROVE',
                             'reason':'합성 규정 버전 검토를 완료했습니다'})
            check('domain_review_approved',change['status']=='PENDING_RELEASE')
            change=api(client,'POST',f'/api/changes/{cid}/release-decision','aurora-approver',
                       json={'expected_revision':change['revision'],'decision':'APPROVE',
                             'reason':'모든 합성 검증 조건을 확인했습니다'})
            check('demo_approval_only',change['status']=='APPROVED_FOR_DEMO')
            evidence=api(client,'GET',f'/api/changes/{cid}/evidence','aurora-auditor')
            check('evidence_matches_approval',evidence['matches_approval'] is True)
            check('record_integrity_verified',evidence['record_integrity_verified'] is True)
            check('audit_chain_valid',evidence['audit_chain_verified'] is True)
            check('no_external_anchor',evidence['external_trust_anchor'] is False)
            report['evidence_manifest_sha256']=evidence['manifest_sha256']
            report['change_id']=cid
            report['result']='PASS'
        app.state.db_engine.dispose()
    target.parent.mkdir(exist_ok=True, parents=True)
    with target.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report,indent=2,ensure_ascii=False))
    print(f"Synthetic E2E smoke: {len(report['checks'])}/{len(report['checks'])} checks passed; report={target}")
    return report

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New report path; existing files are preserved')
    run(output=parser.parse_args().output)
