"""Integration tests: real FastAPI requests, real SQLite FK constraints, synthetic fixtures."""
import os
os.environ['CASEPROOF_DEMO_MODE']='1'
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from service.app import create_app
from service.db import create_tables
from service.models import User, Change, Evaluation, AuditEvent, PolicyRule
from service.seed import seed_demo
from reference.evidence_pack import digest

TOKENS={uid:'integration_test_only_'+uid for uid in ['aurora-analyst','aurora-reviewer','aurora-approver','aurora-auditor','horizon-analyst','horizon-reviewer','horizon-approver']}

@pytest.fixture
def fx(tmp_path):
    dbpath=tmp_path/'caseproof.sqlite3'
    app=create_app(f'sqlite:///{dbpath}',demo_mode=True)
    create_tables(app.state.db_engine)
    with app.state.session_factory() as db:
        seed_demo(db,TOKENS)
        db.commit()
    with TestClient(app) as client:
        yield client,app
    app.state.db_engine.dispose()

def auth(uid): return {'Authorization':'Bearer '+TOKENS[uid]}

def good_request(client,who='aurora-analyst',scope_idx=0):
    scopes=client.get('/api/scopes',headers=auth(who)).json()
    # Choose document-window for predictable 30/20-day scenario.
    matches=[x for x in scopes if x['rule_key']=='DOCUMENT_WINDOW_DAYS']
    s=matches[scope_idx]
    return {'title':'가상 약관 개정 적용일 회귀 검증',
            'product':s['product'],'workflow':s['workflow'],'rule_key':s['rule_key'],
            'dataset_hash':s['dataset_hash'],'evaluator_hash':s['evaluator_hash'],'source_hash':s['source_hash']}

def create(client,who='aurora-analyst'):
    r=client.post('/api/changes',headers=auth(who),json=good_request(client,who))
    assert r.status_code==201,r.text
    return r.json()

def evaluate(client,c,who='aurora-analyst',claim_days=30,basis_date='2026-06-30',riders=None,key=None,revision=None,
             asof='2026-10-28T00:00:00+09:00'):
    request={'claim_days':claim_days,'basis_date':basis_date,'rider_codes':riders or [],'as_of_recorded':asof}
    headers={**auth(who),'X-Expected-Revision':str(revision or c['revision']),
             'Idempotency-Key':key or ('integration-'+uuid4().hex)}
    return client.post(f"/api/changes/{c['id']}/evaluations",headers=headers,json=request)

def ready_for_domain(client):
    c=create(client)
    r=evaluate(client,c)
    assert r.status_code==201,r.text
    assert r.json()['verdict']=='PASS',r.json()
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    second=evaluate(client,c,claim_days=20,basis_date='2026-07-01')
    assert second.status_code==201 and second.json()['verdict']=='PASS',second.text
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    r=client.post(f"/api/changes/{c['id']}/submit",headers=auth('aurora-analyst'),json={'expected_revision':c['revision']})
    assert r.status_code==200,r.text
    return r.json()

def ready_for_release(client):
    c=ready_for_domain(client)
    r=client.post(f"/api/changes/{c['id']}/domain-decision",headers=auth('aurora-reviewer'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.status_code==200,r.text
    return r.json()

def test_health_and_frontend(fx):
    client,_=fx
    assert client.get('/api/health').json()['llm_connected'] is False
    assert client.get('/').status_code==200
    assert 'CaseProof' in client.get('/').text

def test_token_required_and_wrong_token(fx):
    client,_=fx
    assert client.get('/api/changes').status_code==401
    assert client.get('/api/changes',headers={'Authorization':'Bearer invalid'}).status_code==401

def test_separate_tenant_scopes(fx):
    client,_=fx
    a=client.get('/api/scopes',headers=auth('aurora-analyst')).json()
    b=client.get('/api/scopes',headers=auth('horizon-analyst')).json()
    assert {x['product'] for x in a}=={'AUTO-101'}
    assert {x['product'] for x in b}=={'LIFE-201'}

def test_cross_tenant_object_404(fx):
    client,_=fx
    c=create(client)
    assert client.get('/api/changes/'+c['id'],headers=auth('horizon-analyst')).status_code==404
    assert client.get('/api/changes/'+c['id']+'/evidence',headers=auth('horizon-analyst')).status_code==404
    assert client.post('/api/changes/'+c['id']+'/domain-decision',headers=auth('horizon-reviewer'),
                       json={'expected_revision':1,'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'}).status_code==404

def test_no_tenant_id_in_create_contract(fx):
    client,_=fx
    schema=client.get('/openapi.json').json()['components']['schemas']['ChangeCreate']['properties']
    assert 'tenant_id' not in schema and 'requester_id' not in schema

def test_create_and_numeric_pass(fx):
    client,_=fx
    c=create(client)
    r=evaluate(client,c)
    assert r.status_code==201,r.text
    assert r.json()['verdict']=='PASS'
    assert r.json()['result']['expected_days']==30
    details=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    assert details['revision']==2 and len(details['evaluations'])==1

def test_old_version_misused_block(fx):
    client,_=fx
    c=create(client)
    r=evaluate(client,c,claim_days=20)
    assert r.json()['verdict']=='BLOCK'
    assert r.json()['result']['reason']=='NUMERIC_POLICY_MISMATCH'
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    r=client.post('/api/changes/'+c['id']+'/submit',headers=auth('aurora-analyst'),json={'expected_revision':c['revision']})
    assert r.status_code==409 and r.json()['detail']['code']=='FINDINGS_NOT_CLEARED'

def test_effective_date_boundary(fx):
    client,_=fx
    c=create(client)
    r=evaluate(client,c,claim_days=20,basis_date='2026-07-01')
    assert r.status_code==201 and r.json()['verdict']=='PASS'

def test_unknown_rider_inconclusive(fx):
    client,_=fx
    c=create(client)
    assert evaluate(client,c,riders=['INVALID_RIDER']).json()['verdict']=='INCONCLUSIVE'

def test_life_rider_priority(fx):
    client,_=fx
    c=create(client,'horizon-analyst')
    r=evaluate(client,c,'horizon-analyst',claim_days=60,riders=['R-PREMIUM'])
    assert r.status_code==201 and r.json()['verdict']=='PASS'

def test_conflict_rule_inconclusive(fx):
    client,_=fx
    who='horizon-analyst'
    scope=[s for s in client.get('/api/scopes',headers=auth(who)).json() if s['rule_key']=='CONFLICT_EXAMPLE'][0]
    body={**good_request(client,who),'product':scope['product'],'workflow':scope['workflow'],
          'rule_key':scope['rule_key'],'source_hash':scope['source_hash']}
    c=client.post('/api/changes',headers=auth(who),json=body).json()
    r=evaluate(client,c,who,claim_days=10,basis_date='2026-05-01')
    assert r.status_code==201 and r.json()['result']['reason']=='POLICY_CONFLICT'

def test_unapproved_source_inconclusive(fx):
    client,_=fx
    who='horizon-analyst'
    scope=[s for s in client.get('/api/scopes',headers=auth(who)).json() if s['rule_key']=='DRAFT_RULE'][0]
    body={**good_request(client,who),'rule_key':'DRAFT_RULE','source_hash':scope['source_hash']}
    c=client.post('/api/changes',headers=auth(who),json=body).json()
    r=evaluate(client,c,who,claim_days=99)
    assert r.json()['verdict']=='INCONCLUSIVE'
    assert r.json()['result']['reason']=='SOURCE_NOT_APPROVED'

def test_stale_revision_does_not_record(fx):
    client,_=fx
    c=create(client)
    assert evaluate(client,c).status_code==201
    stale=evaluate(client,c,revision=1)
    assert stale.status_code==409 and stale.json()['detail']['code']=='STALE_REVISION'
    assert len(client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()['evaluations'])==1

def test_idempotency_and_conflict(fx):
    client,_=fx
    c=create(client)
    key='integration-same-idempotency-key'
    first=evaluate(client,c,key=key)
    second=evaluate(client,c,key=key)
    other=evaluate(client,c,claim_days=20,key=key)
    assert first.status_code==201 and second.json()['reused'] is True
    assert first.json()['id']==second.json()['id']
    assert other.status_code==409 and other.json()['detail']['code']=='IDEMPOTENCY_CONFLICT'

def test_snapshot_mismatch_rejected(fx):
    client,_=fx
    body=good_request(client)
    body['source_hash']='f'*64
    r=client.post('/api/changes',headers=auth('aurora-analyst'),json=body)
    assert r.status_code==409 and r.json()['detail']['code']=='SNAPSHOT_MISMATCH'

def test_missing_evaluation_blocks_submission(fx):
    client,_=fx
    c=create(client)
    r=client.post('/api/changes/'+c['id']+'/submit',headers=auth('aurora-analyst'),json={'expected_revision':1})
    assert r.status_code==409 and r.json()['detail']['code']=='MANDATORY_TEST_INCOMPLETE'

def test_reviewer_cannot_create_change(fx):
    client,_=fx
    r=client.post('/api/changes',headers=auth('aurora-reviewer'),json=good_request(client))
    assert r.status_code==403

def test_reviewer_cannot_submit(fx):
    client,_=fx
    c=create(client)
    r=client.post('/api/changes/'+c['id']+'/submit',headers=auth('aurora-reviewer'),json={'expected_revision':1})
    assert r.status_code==403

def test_same_requester_cannot_domain_approve_even_if_role_granted(fx):
    client,app=fx
    with app.state.session_factory() as db:
        u=db.get(User,'aurora-analyst')
        u.roles_json='["ANALYST","DOMAIN_REVIEWER"]'
        db.commit()
    c=ready_for_domain(client)
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=auth('aurora-analyst'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.status_code==403 and r.json()['detail']['code']=='SEPARATION_OF_DUTIES'

def test_domain_approval_and_release_with_evidence(fx):
    client,_=fx
    c=ready_for_release(client)
    assert c['status']=='PENDING_RELEASE'
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=auth('aurora-approver'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.status_code==200,r.text
    assert r.json()['status']=='APPROVED_FOR_DEMO'
    assert r.json()['approved_evidence_hash']
    e=client.get('/api/changes/'+c['id']+'/evidence',headers=auth('aurora-analyst')).json()
    assert e['matches_approval'] is True and e['audit_chain_verified'] is True
    assert e['external_trust_anchor'] is False
    assert client.get('/api/audit/verify',headers=auth('aurora-auditor')).json()['verified'] is True

def test_release_approval_role_and_stale(fx):
    client,_=fx
    c=ready_for_release(client)
    path=f"/api/changes/{c['id']}/release-decision"
    assert client.post(path,headers=auth('aurora-reviewer'),
                       json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'}).status_code==403
    r=client.post(path,headers=auth('aurora-approver'),json={'expected_revision':c['revision']-1,'decision':'APPROVE','reason':'업무 분석 결과 최종 승인'})
    assert r.status_code==409 and r.json()['detail']['code']=='STALE_REVISION'

def test_approver_separation_even_if_multirole(fx):
    client,app=fx
    with app.state.session_factory() as db:
        u=db.get(User,'aurora-reviewer')
        u.roles_json='["DOMAIN_REVIEWER","RELEASE_APPROVER"]'
        db.commit()
    c=ready_for_release(client)
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=auth('aurora-reviewer'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.status_code==403 and r.json()['detail']['code']=='SEPARATION_OF_DUTIES'

def test_no_evaluation_after_submission(fx):
    client,_=fx
    c=ready_for_domain(client)
    r=evaluate(client,c)
    assert r.status_code==409 and r.json()['detail']['code']=='INVALID_STATUS'

def test_domain_rejection_requires_reason(fx):
    client,_=fx
    c=ready_for_domain(client)
    r=client.post('/api/changes/'+c['id']+'/domain-decision',headers=auth('aurora-reviewer'),
                  json={'expected_revision':c['revision'],'decision':'REJECT','reason':''})
    assert r.status_code==422

def test_tamper_audit_detected_and_blocks_release(fx):
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        e=db.execute(select(AuditEvent).where(AuditEvent.tenant_id=='AURORA_NONLIFE').order_by(AuditEvent.sequence)).scalars().first()
        e.event_json='{"tampered":true}'
        db.commit()
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=auth('aurora-approver'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.status_code==409 and r.json()['detail']['code']=='AUDIT_INTEGRITY_FAILURE'

def test_tamper_source_detected(fx):
    client,app=fx
    c=create(client)
    with app.state.session_factory() as db:
        p=db.execute(select(PolicyRule).where(PolicyRule.tenant_id=='AURORA_NONLIFE')).scalars().first()
        p.payload_json=p.payload_json.replace('30','31',1)
        db.commit()
    r=evaluate(client,c)
    assert r.status_code==409 and r.json()['detail']['code']=='RULE_SOURCE_TAMPERED'

def test_composite_fk_prevents_cross_tenant_evaluation(fx):
    _,app=fx
    with app.state.session_factory() as db:
        foreign=Change(id='valid-for-a',tenant_id='AURORA_NONLIFE',title='통합 경계 검사',product='AUTO-101',
                       workflow='AUTO_CLAIM_GUIDANCE',rule_key='DOCUMENT_WINDOW_DAYS',requester_id='aurora-analyst',
                       owner_id='aurora-analyst',status='DRAFT',revision=1,dataset_hash='1'*64,
                       evaluator_hash='1'*64,source_hash='1'*64,created_at='2026-01-01',updated_at='2026-01-01')
        db.add(foreign);db.commit()
        db.add(Evaluation(id='attempt',tenant_id='HORIZON_LIFE',change_id='valid-for-a',actor_id='horizon-analyst',
                          idempotency_key='cross-boundary',request_hash='a'*64,request_json='{}',result_json='{}',
                          verdict='PASS',created_at='2026-01-01'))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()

def test_audit_permission_and_tenant_separation(fx):
    client,_=fx
    assert client.get('/api/audit/verify',headers=auth('aurora-analyst')).status_code==403
    assert client.get('/api/audit/verify',headers=auth('aurora-auditor')).json()['tenant_id']=='AURORA_NONLIFE'

def test_release_not_real_deployment(fx):
    client,_=fx
    c=ready_for_release(client)
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=auth('aurora-approver'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'실무 확인 및 승인 의견 기록'})
    assert r.json()['status']=='APPROVED_FOR_DEMO'
    assert client.get('/api/changes/'+c['id']+'/evidence',headers=auth('aurora-approver')).json()['real_release'] is False


def test_fixture_regression_real_db(fx):
    client,_=fx
    a=client.get('/api/fixture-regression',headers=auth('aurora-analyst'))
    b=client.get('/api/fixture-regression',headers=auth('horizon-analyst'))
    assert a.status_code==200 and b.status_code==200
    assert a.json()['failed']==0 and b.json()['failed']==0
    assert a.json()['passed']+b.json()['passed']==20
    assert a.json()['real_llm_evaluation'] is False

def test_one_pass_cannot_bypass_coverage_gate(fx):
    client,_=fx
    c=create(client)
    assert evaluate(client,c).status_code==201
    current=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    r=client.post('/api/changes/'+c['id']+'/submit',headers=auth('aurora-analyst'),json={'expected_revision':current['revision']})
    assert r.status_code==409 and r.json()['detail']['code']=='MANDATORY_TEST_INCOMPLETE'

def test_duplicate_version_does_not_pass_coverage(fx):
    client,_=fx
    c=create(client)
    r=evaluate(client,c)
    assert r.status_code==201
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    assert evaluate(client,c,basis_date='2026-06-25').status_code==201
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    r=client.post('/api/changes/'+c['id']+'/submit',headers=auth('aurora-analyst'),json={'expected_revision':c['revision']})
    assert r.status_code==409 and r.json()['detail']['code']=='INSUFFICIENT_VERSION_COVERAGE'

def test_decision_reason_stored_readable(fx):
    client,_=fx
    c=ready_for_release(client)
    notes=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()['decisions']
    assert len(notes)==1 and notes[0]['reason']=='실무 확인 및 승인 의견 기록'

def test_approval_reason_required(fx):
    client,_=fx
    c=ready_for_release(client)
    r=client.post('/api/changes/'+c['id']+'/release-decision',headers=auth('aurora-approver'),
                  json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'확인'})
    assert r.status_code==422

# v5.1: evidence rows are authenticated against audit event bodies, not only a hash chain.
def test_tampered_evaluation_result_blocks_release(fx):
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        e=db.execute(select(Evaluation).where(Evaluation.change_id==c['id'])).scalars().first()
        data=__import__('json').loads(e.result_json)
        data['expected_days']=999
        e.result_json=__import__('json').dumps(data)
        db.commit()
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==409 and r.json()['detail']['code']=='EVIDENCE_RECORD_TAMPERED'


def test_tampered_evaluation_input_blocks_review_submission(fx):
    client,app=fx
    c=create(client)
    assert evaluate(client,c).status_code==201
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    assert evaluate(client,c,claim_days=20,basis_date='2026-07-01').status_code==201
    with app.state.session_factory() as db:
        e=db.execute(select(Evaluation).where(Evaluation.change_id==c['id'])).scalars().first()
        e.request_json='{"claim_days":20,"basis_date":"2026-07-01"}'
        db.commit()
    c=client.get('/api/changes/'+c['id'],headers=auth('aurora-analyst')).json()
    r=client.post(f"/api/changes/{c['id']}/submit",headers=auth('aurora-analyst'),
        json={'expected_revision':c['revision']})
    assert r.status_code==409 and r.json()['detail']['code']=='EVIDENCE_RECORD_TAMPERED'


def test_deleted_evaluation_blocks_release(fx):
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        e=db.execute(select(Evaluation).where(Evaluation.change_id==c['id'])).scalars().first()
        db.delete(e);db.commit()
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==409 and r.json()['detail']['code']=='EVIDENCE_RECORD_TAMPERED'


def test_tampered_change_scope_blocks_release(fx):
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        row=db.get(Change,c['id']);row.title='원본 제목을 조작한 기록'
        db.commit()
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==409 and r.json()['detail']['code']=='EVIDENCE_RECORD_TAMPERED'


def test_tampered_domain_reason_blocks_release(fx):
    from service.models import DecisionNote
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        note=db.execute(select(DecisionNote).where(DecisionNote.change_id==c['id'])).scalar_one()
        note.reason='조작된 승인 근거입니다';db.commit()
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==409 and r.json()['detail']['code']=='EVIDENCE_RECORD_TAMPERED'


def test_approved_evidence_detects_subsequent_tamper(fx):
    client,app=fx
    c=ready_for_release(client)
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==200,r.text
    before=client.get(f"/api/changes/{c['id']}/evidence",headers=auth('aurora-auditor')).json()
    assert before['record_integrity_verified'] and before['matches_approval']
    with app.state.session_factory() as db:
        e=db.execute(select(Evaluation).where(Evaluation.change_id==c['id'])).scalars().first()
        e.result_json='{"verdict":"PASS","expected_days":1234}'
        db.commit()
    after=client.get(f"/api/changes/{c['id']}/evidence",headers=auth('aurora-auditor')).json()
    assert not after['record_integrity_verified']
    assert not after['matches_approval']
    assert after['audit_chain_verified'] is True  # Proves chain-only verification was insufficient.


def test_corrupt_audit_json_fails_closed_without_server_error(fx):
    client,app=fx
    c=ready_for_release(client)
    with app.state.session_factory() as db:
        e=db.execute(select(AuditEvent).where(AuditEvent.tenant_id=='AURORA_NONLIFE')).scalars().first()
        e.event_json='{INVALID JSON';db.commit()
    r=client.post(f"/api/changes/{c['id']}/release-decision",headers=auth('aurora-approver'),
        json={'expected_revision':c['revision'],'decision':'APPROVE','reason':'추가 검수 후 최종 승인합니다'})
    assert r.status_code==409 and r.json()['detail']['code']=='AUDIT_INTEGRITY_FAILURE'
