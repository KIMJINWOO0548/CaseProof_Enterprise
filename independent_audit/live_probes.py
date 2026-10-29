"""Optional synthetic-only HTTP/SQLite probes for CaseProof v5.1.
AUDIT ARTIFACT: This file does not modify project code, datasets or test answers.
Not executed in the audit environment due to missing FastAPI and SQLAlchemy.
After installing requirements-dev, set CASEPROOF_CURRENT to extracted current/.
"""
import os, sys, tempfile, json
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

root=Path(os.environ['CASEPROOF_CURRENT']).resolve()
sys.path.insert(0,str(root))
os.environ['CASEPROOF_DEMO_MODE']='1'
os.environ['CASEPROOF_DATABASE_URL']='sqlite://'
from fastapi.testclient import TestClient
from service.app import create_app
from service.db import create_tables
from service.seed import seed_demo
from service.models import Change, Evaluation, AuditEvent, User

T={x:'audit_synthetic_'+x for x in ('aurora-analyst','aurora-reviewer','aurora-approver','aurora-auditor','horizon-analyst')}
def headers(u,**kw):return {'Authorization':'Bearer '+T[u],**kw}
def body(client):
    s=next(x for x in client.get('/api/scopes',headers=headers('aurora-analyst')).json() if x['rule_key']=='DOCUMENT_WINDOW_DAYS')
    return {'title':'Synthetic audit test change',**{k:s[k] for k in ('product','workflow','rule_key','dataset_hash','evaluator_hash','source_hash')}}
def post_change(client):
    r=client.post('/api/changes',headers=headers('aurora-analyst'),json=body(client)); assert r.status_code==201,r.text;return r.json()
def evaluate(client,c,days,date,key=None):
    return client.post(f"/api/changes/{c['id']}/evaluations",headers=headers('aurora-analyst',**{'X-Expected-Revision':str(c['revision']),'Idempotency-Key':key or uuid4().hex}),json={'claim_days':days,'basis_date':date,'rider_codes':[],'as_of_recorded':'2026-10-28T00:00:00+09:00'})
def get(client,c):return client.get('/api/changes/'+c['id'],headers=headers('aurora-analyst')).json()
def submitted(client):
    c=post_change(client)
    for days,date in [(30,'2026-06-30'),(20,'2026-07-01')]:
        r=evaluate(client,c,days,date);assert r.status_code==201 and r.json()['verdict']=='PASS',r.text;c=get(client,c)
    r=client.post(f"/api/changes/{c['id']}/submit",headers=headers('aurora-analyst'),json={'expected_revision':c['revision']});assert r.status_code==200,r.text;return r.json()
def make(tmp):
    app=create_app('sqlite:///'+str(Path(tmp)/'probe.sqlite3'),demo_mode=True);create_tables(app.state.db_engine)
    with app.state.session_factory() as s:seed_demo(s,T);s.commit()
    return app

def run(name,fn):
    with tempfile.TemporaryDirectory(prefix='caseproof_audit_') as tmp:
        app=make(tmp)
        try:
            with TestClient(app,raise_server_exceptions=False) as client: fn(client,app)
        finally:app.state.db_engine.dispose()
    print(name,'completed')

def access(client,app):
    c=post_change(client)
    print('invalid token=',client.get('/api/changes',headers={'Authorization':'Bearer wrong'}).status_code)
    print('cross tenant=',client.get('/api/changes/'+c['id'],headers=headers('horizon-analyst')).status_code)
    c=submitted(client)
    with app.state.session_factory() as s:
        u=s.get(User,'aurora-analyst');u.roles_json=json.dumps(['ANALYST','DOMAIN_REVIEWER','RELEASE_APPROVER']);s.commit()
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-analyst'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic self approval'})
    print('self approval=',r.status_code)

def state_tamper(client,app):
    c=submitted(client)
    with app.state.session_factory() as s:
        row=s.get(Change,c['id']);row.status='PENDING_RELEASE';s.commit()
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=headers('aurora-approver'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic approved record'})
    print('state-only tamper release:',r.status_code,r.text)
    e=client.get('/api/changes/'+c['id']+'/evidence',headers=headers('aurora-auditor'))
    print('evidence:',e.status_code,e.text)

def replay(client,app):
    b=body(client);a=client.post('/api/changes',headers=headers('aurora-analyst'),json=b);b2=client.post('/api/changes',headers=headers('aurora-analyst'),json=b)
    print('same change POST:',a.status_code,b2.status_code,'same_id=',a.json().get('id')==b2.json().get('id'))
    c=a.json();k='same-idempotency-key-for-audit';e1=evaluate(client,c,30,'2026-06-30',k);e2=evaluate(client,c,30,'2026-06-30',k)
    print('same evaluation POST:',e1.status_code,e2.status_code,'reused=',e2.json().get('reused'))

def evidence_tamper(client,app):
    c=submitted(client)
    with app.state.session_factory() as s:
        e=s.query(Evaluation).filter_by(change_id=c['id']).first();res=json.loads(e.result_json);res['expected_days']=999;e.result_json=json.dumps(res);s.commit()
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-reviewer'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic approved record'})
    print('result tamper domain decision:',r.status_code,r.text)

def post_approval_tamper(client,app):
    c=submitted(client)
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-reviewer'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic domain approved'})
    assert r.status_code==200,r.text;c=r.json()
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=headers('aurora-approver'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic release approved'})
    assert r.status_code==200,r.text
    with app.state.session_factory() as s:
        e=s.query(Evaluation).filter_by(change_id=c['id']).first();res=json.loads(e.result_json);res['expected_days']=999;e.result_json=json.dumps(res);s.commit()
    r=client.get('/api/changes/'+c['id']+'/evidence',headers=headers('aurora-auditor'))
    print('post-approval result tamper evidence:',r.status_code,r.text)

def missing_evidence(client,app):
    c=submitted(client)
    with app.state.session_factory() as s:
        e=s.query(Evaluation).filter_by(change_id=c['id']).first();s.delete(e);s.commit()
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-reviewer'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic domain approved'})
    print('missing evaluation domain decision:',r.status_code,r.text)

def audit_tamper(client,app):
    c=submitted(client)
    with app.state.session_factory() as s:
        ev=s.query(AuditEvent).filter_by(tenant_id='AURORA_NONLIFE').first();ev.event_hash='f'*64;s.commit()
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-reviewer'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic approved record'})
    print('audit tamper domain decision:',r.status_code,r.text)

def competition(client,app):
    c=submitted(client)
    def send(_):
        r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=headers('aurora-reviewer'),json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'Synthetic approved record'})
        return r.status_code
    with ThreadPoolExecutor(max_workers=2) as ex:statuses=list(ex.map(send,range(2)))
    print('simultaneous domain approvals:',statuses,'success_count=',sum(x==200 for x in statuses))

for name,fn in [('AUTH_ISOLATION',access),('STATE_TAMPER_P0_CANDIDATE',state_tamper),('REPLAY',replay),('RESULT_TAMPER',evidence_tamper),('POST_APPROVAL_TAMPER',post_approval_tamper),('MISSING_EVIDENCE',missing_evidence),('AUDIT_TAMPER',audit_tamper),('COMPETITION',competition)]:run(name,fn)
