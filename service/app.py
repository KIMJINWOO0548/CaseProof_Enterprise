"""CaseProof Enterprise v5: functional local MVP, synthetic insurance rules only.

Deliberate exclusions: real model calls, insurance claim decisions, external source
approval, SSO, independent WORM audit anchor and production release automation.
"""
from __future__ import annotations
import hashlib, json, os, secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Header, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .db import make_engine, session_factory, create_tables
from .models import Tenant, User, PolicyRule, Change, Evaluation, AuditEvent, DecisionNote, ChangeTransition
from .integrity import transitions, transition_data, projection_issues, approval_envelope
from .schemas import ChangeCreate, EvalRequest, Transition, Decision, RevisionHeader
from .idempotency import fingerprint, replay, finish
from reference.verify_answer import verify_numeric_claim
from reference.resolver import resolve
from reference.evidence_pack import canonical_json, digest

ZERO = '0'*64
MALFORMED = (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError)
ROOT = Path(__file__).resolve().parents[1]
DATASET_HASH = hashlib.sha256((ROOT/'datasets'/'resolver_test_cases.json').read_bytes()).hexdigest()
EVALUATOR_HASH = hashlib.sha256((ROOT/'reference'/'resolver.py').read_bytes() +
                                 (ROOT/'reference'/'verify_answer.py').read_bytes()).hexdigest()
security = HTTPBearer(auto_error=False)

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def error(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={'code':code,'message':message})

def json_obj(text):
    return json.loads(text)

def parse_audit_event(row):
    event=json_obj(row.event_json)
    if not isinstance(event,dict) or not isinstance(event.get('details'),dict):
        raise ValueError('audit event and details must be objects')
    if any(not isinstance(event.get(key),str) or not event[key]
           for key in ('actor_id','subject_id','kind','at')):
        raise ValueError('audit identity fields are required')
    if event['actor_id']!=row.actor_id:
        raise ValueError('audit actor column differs from event')
    return event

def audit_ok(db:Session, tenant_id:str) -> bool:
    """Detect event mutations against the DB's current head (NOT WORM/independent anchoring)."""
    tenant = db.get(Tenant,tenant_id)
    events = db.execute(select(AuditEvent).where(AuditEvent.tenant_id==tenant_id).order_by(AuditEvent.sequence)).scalars().all()
    prev = ZERO
    for i,item in enumerate(events,1):
        if item.sequence!=i or item.prev_hash!=prev:
            return False
        try:
            data = {'sequence':i,'prev_hash':prev,'event':parse_audit_event(item)}
            if item.event_hash != digest(data):
                return False
        except MALFORMED:
            return False
        prev = item.event_hash
    return bool(tenant and tenant.audit_seq==len(events) and tenant.audit_head==prev)


def record_integrity(db:Session, change:Change) -> tuple[bool,list[str]]:
    """Check that mutable SQL rows still agree with the original append-only audit events.

    Scope is deliberately limited: a privileged DB administrator who can rewrite ALL
    audit events and head hashes is not defeated. That needs an external trust anchor.
    """
    evs=db.execute(select(AuditEvent).where(AuditEvent.tenant_id==change.tenant_id)
                   .order_by(AuditEvent.sequence)).scalars().all()
    issues=[]
    try:
        parsed=[(e,parse_audit_event(e)) for e in evs]
        scoped_rows=[(e,body) for e,body in parsed if body['subject_id']==change.id]
        scoped=[body for _,body in scoped_rows]
    except MALFORMED:
        return False,['AUDIT_JSON_INVALID']
    # The tenant audit order must agree with the independently stored transition order.
    if [e.id for e,_ in scoped_rows]!=[t.audit_event_id for t in transitions(db,change)]:
        issues.append('TRANSITION_AUDIT_ORDER_MISMATCH')
    for revision,event in enumerate(scoped,1):
        if event['kind']=='EVALUATION_RECORDED':
            prior=event['details'].get('revision_from')
            if type(prior) is not int or prior!=revision-1:
                issues.append('EVALUATION_REVISION_MISMATCH')
    created=[e for e in scoped if e['kind']=='CHANGE_CREATED']
    if len(created)!=1:
        issues.append('CHANGE_CREATION_EVENT_MISSING_OR_DUPLICATE')
    else:
        expected=created[0]['details'].get('snapshot')
        actual={k:getattr(change,k) for k in ('tenant_id','title','product','workflow','rule_key',
                     'requester_id','owner_id','dataset_hash','evaluator_hash','source_hash','created_at')}
        if expected!=actual:
            issues.append('CHANGE_SNAPSHOT_MISMATCH')
    # Every evaluation must have exactly one audit event binding body, verdict and result.
    evaluations=db.execute(select(Evaluation).where(Evaluation.tenant_id==change.tenant_id,
                           Evaluation.change_id==change.id)).scalars().all()
    eval_events=[e for e in scoped if e['kind']=='EVALUATION_RECORDED']
    if any(not isinstance(e['details'].get('evaluation_id'),str) or not e['details']['evaluation_id']
           for e in eval_events):
        return False,['EVALUATION_AUDIT_ID_INVALID']
    event_lookup={e['details'].get('evaluation_id'):e for e in eval_events}
    if len(event_lookup)!=len(eval_events) or set(event_lookup)!={e.id for e in evaluations}:
        issues.append('EVALUATION_AUDIT_SET_MISMATCH')
    for ev in evaluations:
        event=event_lookup.get(ev.id)
        try:
            result=json_obj(ev.result_json)
            request=json_obj(ev.request_json)
            checks=bool(isinstance(request,dict) and isinstance(result,dict)
                and event and ev.request_hash==digest(request)
                and event['details']['request_sha256']==ev.request_hash
                and event['details']['result_sha256']==digest(result)
                and event['details']['verdict']==ev.verdict
                and result['verdict']==ev.verdict
                and event['actor_id']==ev.actor_id)
        except MALFORMED:
            checks=False
        if not checks:
            issues.append('EVALUATION_RECORD_MISMATCH:'+ev.id)
    notes=db.execute(select(DecisionNote).where(DecisionNote.tenant_id==change.tenant_id,
                      DecisionNote.change_id==change.id)).scalars().all()
    decision_events=[e for e in scoped if e['kind'] in ('DOMAIN_APPROVE','DOMAIN_REJECT',
                                                         'RELEASE_APPROVE','RELEASE_REJECT','APPROVED_FOR_DEMO')]
    if any(not isinstance(e['details'].get('decision_id'),str) or not e['details']['decision_id']
           for e in decision_events):
        return False,['DECISION_AUDIT_ID_INVALID']
    event_by_note={e['details'].get('decision_id'):e for e in decision_events}
    if len(event_by_note)!=len(decision_events) or set(event_by_note)!={n.id for n in notes}:
        issues.append('DECISION_AUDIT_SET_MISMATCH')
    for note in notes:
        event=event_by_note.get(note.id)
        try:
            expected_kind=('DOMAIN_'+note.decision if note.stage=='DOMAIN' else
                           ('APPROVED_FOR_DEMO' if note.decision=='APPROVE' else 'RELEASE_REJECT'))
            checks=bool(event and event['kind']==expected_kind and
                        event['details']['reason_sha256']==hashlib.sha256(note.reason.encode()).hexdigest()
                        and event['actor_id']==note.actor_id and
                        event['details']['stage']==note.stage and
                        event['details']['decision']==note.decision)
        except MALFORMED:
            checks=False
        if not checks:
            issues.append('DECISION_RECORD_MISMATCH:'+note.id)
    issues.extend(projection_issues(db,change))
    return not issues,issues


def require_integrity(db:Session, change:Change):
    if not audit_ok(db,change.tenant_id):
        error(409,'AUDIT_INTEGRITY_FAILURE','감사 이벤트 해시 체인이 일치하지 않습니다.')
    ok,issues=record_integrity(db,change)
    if not ok:
        error(409,'EVIDENCE_RECORD_TAMPERED','감사 이벤트와 실제 DB 기록이 다릅니다: '+issues[0])

def append_audit(db:Session, tenant_id:str, actor_id:str, kind:str, obj_id:str, details:dict|None=None):
    # PostgreSQL locks the tenant's audit head until commit; SQLite demo is 1-worker only.
    tenant=db.execute(select(Tenant).where(Tenant.id==tenant_id).with_for_update()).scalar_one()
    db.flush()
    c=db.execute(select(Change).where(Change.tenant_id==tenant_id, Change.id==obj_id)).scalar_one()
    prior=transitions(db,c)
    seq=tenant.audit_seq+1
    event_id=str(uuid4())
    details=dict(details or {})
    note=db.get(DecisionNote,details['decision_id']) if details.get('decision_id') else None
    at=note.created_at if note else utcnow()
    t=ChangeTransition(id=str(uuid4()),tenant_id=tenant_id,change_id=obj_id,
        revision_from=prior[-1].revision_to if prior else 0, revision_to=c.revision,
        from_state=prior[-1].to_state if prior else 'NONE',to_state=c.status,kind=kind,
        actor_id=actor_id,decision_id=details.get('decision_id'),
        evidence_hash=details.get('evidence_sha256'),audit_event_id=event_id,
        occurred_at=at,schema_version=1)
    details['transition']=transition_data(t)
    ev={'actor_id':actor_id,'at':at,'kind':kind,'subject_id':obj_id,'details':details}
    envelope={'sequence':seq,'prev_hash':tenant.audit_head,'event':ev}
    hashed=digest(envelope)
    db.add(AuditEvent(id=event_id,tenant_id=tenant_id,actor_id=actor_id,
                      sequence=seq,prev_hash=tenant.audit_head,event_json=canonical_json(ev).decode(),event_hash=hashed))
    tenant.audit_seq=seq
    tenant.audit_head=hashed
    db.flush()
    db.add(t)
    if kind=='APPROVED_FOR_DEMO':
        sealed=approval_envelope(t)
        c.approval_envelope_json=canonical_json(sealed).decode()
        c.approval_envelope_hash=digest(sealed)
    db.flush()


def payload(change:Change, db:Session, include_evals=False):
    data={k:getattr(change,k) for k in ('id','title','product','workflow','rule_key','status','revision','requester_id',
                'owner_id','domain_reviewer_id','release_approver_id','created_at','updated_at','approved_evidence_hash')}
    if include_evals:
        evs=db.execute(select(Evaluation).where(Evaluation.tenant_id==change.tenant_id,
                           Evaluation.change_id==change.id).order_by(Evaluation.created_at, Evaluation.id)).scalars().all()
        data['evaluations']=[{'id':e.id,'verdict':e.verdict,'result':json_obj(e.result_json),'created_at':e.created_at} for e in evs]
        notes=db.execute(select(DecisionNote).where(DecisionNote.tenant_id==change.tenant_id,DecisionNote.change_id==change.id).order_by(DecisionNote.created_at)).scalars().all()
        data['decisions']=[{'stage':n.stage,'decision':n.decision,'actor_id':n.actor_id,'reason':n.reason,'at':n.created_at} for n in notes]
    return data

def scope_rules(db:Session,tenant_id:str,product:str,workflow:str,rule_key:str):
    scope=[]
    for rec in db.execute(select(PolicyRule).where(PolicyRule.tenant_id==tenant_id)).scalars():
        r=json_obj(rec.payload_json)
        if not all(r[k]==v for k,v in {'tenant':tenant_id,'product':product,
                                      'workflow':workflow,'rule_key':rule_key}.items()):
            continue
        # The source digest must still match the actual stored payload.
        if hashlib.sha256(rec.payload_json.encode()).hexdigest()!=rec.source_sha256:
            error(409,'RULE_SOURCE_TAMPERED','규정 원본 스냅샷의 해시가 일치하지 않습니다.')
        scope.append((r,rec.source_sha256))
    return scope

def scope_hash(scope):
    return digest(sorted((r['rule_id'],h) for r,h in scope))

def evidence_content(db:Session, c:Change):
    evs=db.execute(select(Evaluation).where(Evaluation.tenant_id==c.tenant_id,
                           Evaluation.change_id==c.id).order_by(Evaluation.id)).scalars().all()
    rules=scope_rules(db,c.tenant_id,c.product,c.workflow,c.rule_key)
    upper=c.assessment_revision if c.assessment_revision is not None else c.revision
    history=[t for t in transitions(db,c) if t.revision_to<=upper]
    domains=db.scalars(select(DecisionNote).where(DecisionNote.tenant_id==c.tenant_id,
        DecisionNote.change_id==c.id,DecisionNote.stage=='DOMAIN').order_by(DecisionNote.id)).all()
    events={e.id:e for e in db.scalars(select(AuditEvent).where(AuditEvent.tenant_id==c.tenant_id))}
    return {
        'schema':'assessment_manifest_v1','pre_approval_revision':upper,
        'model_hash':None,'prompt_hash':None,
        'transitions':[transition_data(t) for t in history],
        'events':[{'id':t.audit_event_id,'sha256':events[t.audit_event_id].event_hash if t.audit_event_id in events else None} for t in history],
        'domain_decisions':[{'id':n.id,'actor_id':n.actor_id,'decision':n.decision,
                             'reason':n.reason,'created_at':n.created_at} for n in domains],'tenant_id':c.tenant_id,'change_id':c.id,
        'created_at':c.created_at,'source_snapshot_hash':c.source_hash,
        'dataset_hash':c.dataset_hash,'evaluator_hash':c.evaluator_hash,
        'rule_source_hashes':sorted(h for _,h in rules),
        'evaluations':[{'id':e.id,'request_hash':e.request_hash,'result_hash':digest(json_obj(e.result_json))}
                       for e in evs],
    }

def get_change(db:Session, tenant_id:str, cid:str, lock=False) -> Change:
    if lock:
        db.execute(select(Tenant).where(Tenant.id==tenant_id).with_for_update()).scalar_one()
    query=select(Change).where(Change.id==cid,Change.tenant_id==tenant_id)
    c=db.execute(query.with_for_update() if lock else query).scalar_one_or_none()
    if not c:
        error(404,'NOT_FOUND','해당 변경 요청이 존재하지 않습니다.')
    return c

def revision_update(db:Session,c:Change,expected:int,new_state:str|None=None,**extra):
    if c.revision!=expected:
        error(409,'STALE_REVISION','다른 사용자가 먼저 수정했습니다. 화면을 새로고침하세요.')
    values=dict(extra)
    values['revision']=Change.revision+1
    values['updated_at']=utcnow()
    if new_state:
        values['status']=new_state
    result=db.execute(update(Change).where(Change.id==c.id,Change.tenant_id==c.tenant_id,
                                           Change.revision==expected,Change.status==c.status).values(**values))
    if result.rowcount!=1:
        error(409,'STALE_REVISION','변경 도중 충돌이 발생했습니다.')
    db.refresh(c)

def create_app(database_url:str|None=None, demo_mode:bool|None=None):
    demo=demo_mode if demo_mode is not None else os.getenv('CASEPROOF_DEMO_MODE','0')=='1'
    if not demo:
        raise RuntimeError('Only explicit synthetic demo mode is supported; non-demo startup is disabled')
    url=database_url or os.getenv('CASEPROOF_DATABASE_URL','')
    if not url:
        url='sqlite:///./caseproof_demo.sqlite3'
    engine=make_engine(url)
    SessionLocal=session_factory(engine)
    app=FastAPI(title='CaseProof (Synthetic Demo)',version='5.3.0.dev0',
                description='Local demonstration API, NOT insurance or regulatory certification')
    app.state.db_engine=engine
    app.state.session_factory=SessionLocal
    app.state.demo_mode=demo

    def get_db(request:Request):
        with SessionLocal() as db:
            try:
                # SQLite has no row locks: reserve its writer before any auth/state reads.
                mutation_routes={'/api/changes','/api/changes/{cid}/evaluations',
                    '/api/changes/{cid}/submit','/api/changes/{cid}/domain-decision',
                    '/api/changes/{cid}/release-decision'}
                if (engine.dialect.name=='sqlite' and request.method=='POST'
                    and request.scope['route'].path in mutation_routes):
                    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
                yield db
            except OperationalError as exc:
                db.rollback()
                if engine.dialect.name=='sqlite' and getattr(exc.orig,'sqlite_errorcode',0) & 255 in (5,6):
                    raise HTTPException(409,detail={'code':'RETRYABLE_CONFLICT',
                        'message':'동시 요청 처리 중입니다. 같은 키로 재시도하세요.','retryable':True},
                        headers={'Retry-After':'1'}) from exc
                raise
            except Exception:
                db.rollback()
                raise

    def get_actor(auth:HTTPAuthorizationCredentials|None=Security(security),db:Session=Depends(get_db)):
        if not auth or auth.scheme.lower()!='bearer' or not auth.credentials:
            error(401,'UNAUTHENTICATED','Bearer 토큰이 필요합니다.')
        h=hashlib.sha256(auth.credentials.encode()).hexdigest()
        actor=db.execute(select(User).where(User.token_hash==h,User.enabled==True)).scalar_one_or_none()
        if actor is None:
            error(401,'UNAUTHENTICATED','인증되지 않은 토큰입니다.')
        return actor

    def require(actor:User,role:str):
        if role not in json_obj(actor.roles_json):
            error(403,'PERMISSION_DENIED',f'{role} 역할이 필요합니다.')

    def safe_commit(db:Session):
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    @app.get('/')
    def dashboard():
        return FileResponse(ROOT/'service'/'static'/'index.html')

    @app.get('/api/health')
    def health():
        return {'status':'ok','mode':'SYNTHETIC_LOCAL_DEMO' if demo else 'NON_DEMO',
                'real_insurance_decisions':False,'llm_connected':False}

    @app.get('/api/me')
    def me(actor:User=Depends(get_actor)):
        return {'id':actor.id,'label':actor.label,'tenant_id':actor.tenant_id,'roles':json_obj(actor.roles_json)}

    @app.get('/api/rules')
    def list_rules(actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        records=db.execute(select(PolicyRule).where(PolicyRule.tenant_id==actor.tenant_id)).scalars().all()
        return [{'rule_id':r.id,'source_sha256':r.source_sha256,**json_obj(r.payload_json)} for r in records]

    @app.get('/api/scopes')
    def list_scopes(actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        keys=set()
        for r in db.execute(select(PolicyRule).where(PolicyRule.tenant_id==actor.tenant_id)).scalars():
            v=json_obj(r.payload_json)
            keys.add((v['product'],v['workflow'],v['rule_key']))
        scopes=[]
        for product,workflow,rule_key in sorted(keys):
            records=scope_rules(db,actor.tenant_id,product,workflow,rule_key)
            scopes.append({'product':product,'workflow':workflow,'rule_key':rule_key,
                           'source_hash':scope_hash(records),'dataset_hash':DATASET_HASH,
                           'evaluator_hash':EVALUATOR_HASH,
                           'date_bases':sorted({r['date_basis'] for r,_ in records})})
        return scopes

    @app.get('/api/fixture-regression')
    def fixture_regression(actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        """Deterministic regression against the package's 20 hand-authored synthetic cases.
        This is NOT an LLM accuracy benchmark or a live insurance qualification.
        """
        require(actor,'ANALYST')
        fixture=json.loads((ROOT/'datasets'/'resolver_test_cases.json').read_text(encoding='utf-8'))
        tenant_rules=[json_obj(r.payload_json) for r in db.execute(select(PolicyRule).where(PolicyRule.tenant_id==actor.tenant_id)).scalars()]
        # Enforce integrity on the entire tenant source set before testing.
        for r in db.execute(select(PolicyRule).where(PolicyRule.tenant_id==actor.tenant_id)).scalars():
            if hashlib.sha256(r.payload_json.encode()).hexdigest()!=r.source_sha256:
                error(409,'RULE_SOURCE_TAMPERED','회귀 실험 전에 소스 변조가 발견되었습니다.')
        rows=[]
        for case in fixture['cases']:
            if case['input'].get('tenant')!=actor.tenant_id:
                continue
            query={**case['input'],'as_of_recorded':case['input'].get('as_of_recorded',fixture['default_recorded'])}
            outcome=resolve(query,tenant_rules)
            expected=case['expected']
            ok=(outcome.status==expected['status'] and
                (not expected.get('reason') or expected['reason'] in outcome.reason_codes) and
                ('value' not in expected or expected['value']==outcome.value) and
                ('rule_id' not in expected or expected['rule_id']==outcome.rule_id))
            rows.append({'case_id':case['id'],'passed':ok,'status':outcome.status,
                         'reason_codes':outcome.reason_codes,'expected':expected,
                         'resolved_rule_id':outcome.rule_id})
        return {'tenant_id':actor.tenant_id,'total':len(rows),'passed':sum(x['passed'] for x in rows),
                'failed':sum(not x['passed'] for x in rows),'dataset_sha256':DATASET_HASH,
                'evaluator_sha256':EVALUATOR_HASH,'cases':rows,
                'real_llm_evaluation':False,'expert_reviewed':False}

    @app.get('/api/changes')
    def list_changes(actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        items=db.execute(select(Change).where(Change.tenant_id==actor.tenant_id).order_by(Change.created_at.desc())).scalars().all()
        return [payload(c,db) for c in items]

    @app.post('/api/changes',status_code=201)
    def new_change(req:ChangeCreate,
                   idempotency_key:str=Header(...,alias='Idempotency-Key',min_length=12,max_length=128),
                   actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'ANALYST')
        db.execute(select(Tenant).where(Tenant.id==actor.tenant_id).with_for_update()).scalar_one()
        request_hash=fingerprint('create',None,req.model_dump(mode='json'),None)
        previous=replay(db,actor,idempotency_key,'create',request_hash)
        if previous is not None:
            return previous
        if not audit_ok(db,actor.tenant_id):
            error(409,'AUDIT_INTEGRITY_FAILURE','기존 감사 체인이 일치하지 않아 새 변경을 만들 수 없습니다.')
        # Scope the rule to the authenticated user's tenant; never accept a tenant ID from the client.
        scope=scope_rules(db,actor.tenant_id,req.product,req.workflow,req.rule_key)
        if not scope:
            error(422,'UNKNOWN_RULE_SCOPE','가상 업무팩에 등록되지 않은 상품/업무/규칙입니다.')
        if req.source_hash!=scope_hash(scope) or req.dataset_hash!=DATASET_HASH or req.evaluator_hash!=EVALUATOR_HASH:
            error(409,'SNAPSHOT_MISMATCH','서버에 고정된 데이터셋·평가자·출처 해시와 일치하지 않습니다.')
        now=utcnow()
        c=Change(id=str(uuid4()),tenant_id=actor.tenant_id,title=req.title,product=req.product,
                 workflow=req.workflow,rule_key=req.rule_key,requester_id=actor.id,owner_id=actor.id,
                 status='DRAFT',revision=1,dataset_hash=req.dataset_hash,evaluator_hash=req.evaluator_hash,
                 source_hash=req.source_hash,created_at=now,updated_at=now)
        db.add(c)
        append_audit(db,actor.tenant_id,actor.id,'CHANGE_CREATED',c.id,
                     {'snapshot':{k:getattr(c,k) for k in ('tenant_id','title','product','workflow','rule_key',
                       'requester_id','owner_id','dataset_hash','evaluator_hash','source_hash','created_at')}})
        response=finish(db,actor,idempotency_key,'create',request_hash,c,payload(c,db),201)
        safe_commit(db)
        return response

    @app.get('/api/changes/{cid}')
    def detail(cid:str,actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        return payload(get_change(db,actor.tenant_id,cid),db,include_evals=True)

    @app.post('/api/changes/{cid}/evaluations',status_code=201)
    def evaluate(cid:str,req:EvalRequest,expected_revision:Annotated[RevisionHeader, Header(alias='X-Expected-Revision', description='Canonical positive decimal header; no sign, whitespace, decimal point or leading zero.', json_schema_extra={'minimum':1})],
                 idempotency_key:str=Header(...,alias='Idempotency-Key',min_length=12,max_length=128),
                 actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'ANALYST')
        c=get_change(db,actor.tenant_id,cid,lock=True)
        if c.requester_id!=actor.id:
            error(403,'REQUESTER_ONLY','최초 요청자만 평가할 수 있습니다.')
        data=req.model_dump(mode='json')
        body_hash=digest(data)
        request_hash=fingerprint('evaluations',cid,data,expected_revision)
        previous=replay(db,actor,idempotency_key,'evaluations',request_hash)
        if previous is not None:
            return previous
        require_integrity(db,c)
        if c.status!='DRAFT':
            error(409,'INVALID_STATUS','DRAFT에서만 새 검증을 실행할 수 있습니다.')
        # In this narrow working slice, exactly one date basis is supported per scope.
        pairs=scope_rules(db,actor.tenant_id,c.product,c.workflow,c.rule_key)
        if scope_hash(pairs)!=c.source_hash:
            error(409,'SOURCE_CHANGED','등록 후 규정 스냅샷이 변경되어 재검증이 필요합니다.')
        scoped=[r for r,_ in pairs]
        bases={r['date_basis'] for r in scoped}
        if len(bases)!=1:
            error(422,'AMBIGUOUS_DATE_BASIS','동일 스코프의 날짜 기준이 달라 담당자 검토가 필요합니다.')
        date_basis=next(iter(bases))
        query={'tenant':actor.tenant_id,'product':c.product,'workflow':c.workflow,'rule_key':c.rule_key,
               date_basis:req.basis_date.isoformat(),'rider_codes':req.rider_codes,
               'as_of_recorded':req.as_of_recorded.isoformat()}
        if req.requested_policy_version:
            query['requested_policy_version']=req.requested_policy_version
        result=verify_numeric_claim(query,req.claim_days,scoped)
        rev=c.revision
        revision_update(db,c,expected_revision)
        e=Evaluation(id=str(uuid4()),tenant_id=actor.tenant_id,change_id=c.id,actor_id=actor.id,
                     idempotency_key=idempotency_key,request_hash=body_hash,
                     request_json=canonical_json(data).decode(),result_json=canonical_json(result).decode(),
                     verdict=result['verdict'],created_at=utcnow())
        db.add(e)
        append_audit(db,actor.tenant_id,actor.id,'EVALUATION_RECORDED',c.id,
                     {'evaluation_id':e.id,'verdict':e.verdict,'revision_from':rev,
                      'request_sha256':e.request_hash,'result_sha256':digest(result)})
        response=finish(db,actor,idempotency_key,'evaluations',request_hash,c,
            {'id':e.id,'verdict':result['verdict'],'result':result,'reused':False,'revision':c.revision},201)
        safe_commit(db)
        return response

    @app.post('/api/changes/{cid}/submit')
    def submit(cid:str,req:Transition,
               idempotency_key:str=Header(...,alias='Idempotency-Key',min_length=12,max_length=128),
               actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'ANALYST')
        c=get_change(db,actor.tenant_id,cid,lock=True)
        if c.requester_id!=actor.id:
            error(403,'REQUESTER_ONLY','최초 요청자만 검토를 요청할 수 있습니다.')
        request_hash=fingerprint('submit',cid,req.model_dump(mode='json'),req.expected_revision)
        previous=replay(db,actor,idempotency_key,'submit',request_hash)
        if previous is not None:
            return previous
        require_integrity(db,c)
        if c.status!='DRAFT':
            error(409,'INVALID_STATUS','검토 요청 가능한 상태가 아닙니다.')
        if (scope_hash(scope_rules(db,c.tenant_id,c.product,c.workflow,c.rule_key))!=c.source_hash
            or c.dataset_hash!=DATASET_HASH or c.evaluator_hash!=EVALUATOR_HASH):
            error(409,'SNAPSHOT_MISMATCH','출처/평가자/데이터셋이 변경되어 승인할 수 없습니다.')
        evs=db.execute(select(Evaluation).where(Evaluation.tenant_id==actor.tenant_id,Evaluation.change_id==cid)).scalars().all()
        if any(e.verdict!='PASS' for e in evs):
            error(409,'FINDINGS_NOT_CLEARED','BLOCK 또는 INCONCLUSIVE가 남아 있습니다.')
        if len(evs)<2:
            error(409,'MANDATORY_TEST_INCOMPLETE','서로 다른 버전의 최소 두 가지 검증 결과가 필요합니다.')
        versions={json_obj(e.result_json).get('resolved_rule_id') for e in evs}
        if len(versions)<2 or None in versions:
            error(409,'INSUFFICIENT_VERSION_COVERAGE','최소 2개의 서로 다른 적용 규정 버전을 검증해야 합니다.')
        revision_update(db,c,req.expected_revision,'PENDING_DOMAIN_REVIEW')
        append_audit(db,actor.tenant_id,actor.id,'SUBMITTED_FOR_DOMAIN_REVIEW',c.id)
        response=finish(db,actor,idempotency_key,'submit',request_hash,c,payload(c,db),200)
        safe_commit(db)
        return response

    @app.post('/api/changes/{cid}/domain-decision')
    def domain_review(cid:str,req:Decision,
                      idempotency_key:str=Header(...,alias='Idempotency-Key',min_length=12,max_length=128),
                      actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'DOMAIN_REVIEWER')
        c=get_change(db,actor.tenant_id,cid,lock=True)
        if actor.id in (c.requester_id,c.owner_id):
            error(403,'SEPARATION_OF_DUTIES','요청자는 자신의 변경을 검토할 수 없습니다.')
        request_hash=fingerprint('domain-decision',cid,req.model_dump(mode='json'),req.expected_revision)
        previous=replay(db,actor,idempotency_key,'domain-decision',request_hash)
        if previous is not None:
            return previous
        if c.status!='PENDING_DOMAIN_REVIEW':
            error(409,'INVALID_STATUS','현업 검토 대기 상태가 아닙니다.')
        require_integrity(db,c)
        state='REJECTED' if req.decision=='REJECT' else 'PENDING_RELEASE'
        revision_update(db,c,req.expected_revision,state,domain_reviewer_id=actor.id)
        note=DecisionNote(id=str(uuid4()),tenant_id=actor.tenant_id,change_id=c.id,
            actor_id=actor.id,stage='DOMAIN',decision=req.decision,reason=req.reason.strip(),created_at=utcnow())
        db.add(note)
        append_audit(db,actor.tenant_id,actor.id,'DOMAIN_'+req.decision,c.id,
                     {'decision_id':note.id,'stage':'DOMAIN','decision':req.decision,
                      'reason_sha256':hashlib.sha256(note.reason.encode()).hexdigest()})
        response=finish(db,actor,idempotency_key,'domain-decision',request_hash,c,payload(c,db),200)
        safe_commit(db)
        return response

    @app.post('/api/changes/{cid}/release-decision')
    def release_review(cid:str,req:Decision,
                       idempotency_key:str=Header(...,alias='Idempotency-Key',min_length=12,max_length=128),
                       actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'RELEASE_APPROVER')
        c=get_change(db,actor.tenant_id,cid,lock=True)
        if actor.id in (c.requester_id,c.owner_id,c.domain_reviewer_id):
            error(403,'SEPARATION_OF_DUTIES','요청·검토 담당자와 승인자를 분리해야 합니다.')
        request_hash=fingerprint('release-decision',cid,req.model_dump(mode='json'),req.expected_revision)
        previous=replay(db,actor,idempotency_key,'release-decision',request_hash)
        if previous is not None:
            return previous
        if c.status!='PENDING_RELEASE':
            error(409,'INVALID_STATUS','배포 승인 대기 상태가 아닙니다.')
        require_integrity(db,c)
        if req.decision=='REJECT':
            revision_update(db,c,req.expected_revision,'REJECTED',release_approver_id=actor.id)
            note=DecisionNote(id=str(uuid4()),tenant_id=actor.tenant_id,change_id=c.id,
                actor_id=actor.id,stage='RELEASE',decision='REJECT',reason=req.reason.strip(),created_at=utcnow())
            db.add(note)
            append_audit(db,actor.tenant_id,actor.id,'RELEASE_REJECT',c.id,
                         {'decision_id':note.id,'stage':'RELEASE','decision':'REJECT',
                          'reason_sha256':hashlib.sha256(note.reason.encode()).hexdigest()})
        else:
            evs=db.execute(select(Evaluation).where(Evaluation.tenant_id==actor.tenant_id,
                           Evaluation.change_id==cid)).scalars().all()
            if len(evs)<2 or any(x.verdict!='PASS' for x in evs) or len({json_obj(x.result_json).get('resolved_rule_id') for x in evs})<2:
                error(409,'RELEASE_GATE_BLOCKED','검증 항목이 누락되었거나 차단 결과가 있습니다.')
            if (scope_hash(scope_rules(db,c.tenant_id,c.product,c.workflow,c.rule_key))!=c.source_hash
                or c.dataset_hash!=DATASET_HASH or c.evaluator_hash!=EVALUATOR_HASH):
                error(409,'SNAPSHOT_MISMATCH','출시 승인 전 스냅샷 변경이 확인되었습니다.')
            manifest_hash=digest(evidence_content(db,c))
            revision_update(db,c,req.expected_revision,'APPROVED_FOR_DEMO',
                            release_approver_id=actor.id,approved_evidence_hash=manifest_hash,assessment_revision=c.revision)
            note=DecisionNote(id=str(uuid4()),tenant_id=actor.tenant_id,change_id=c.id,
                actor_id=actor.id,stage='RELEASE',decision='APPROVE',reason=req.reason.strip(),created_at=utcnow())
            db.add(note)
            append_audit(db,actor.tenant_id,actor.id,'APPROVED_FOR_DEMO',c.id,
                         {'decision_id':note.id,'stage':'RELEASE','decision':'APPROVE',
                          'reason_sha256':hashlib.sha256(note.reason.encode()).hexdigest(),
                          'evidence_sha256':manifest_hash})
        response=finish(db,actor,idempotency_key,'release-decision',request_hash,c,payload(c,db),200)
        safe_commit(db)
        return response

    @app.get('/api/changes/{cid}/evidence')
    def get_evidence(cid:str,actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        c=get_change(db,actor.tenant_id,cid)
        verified, issues=record_integrity(db,c)
        try:
            content=evidence_content(db,c)
            h=digest(content)
        except MALFORMED:
            content,h,verified=None,None,False
            issues=[*issues,'EVIDENCE_CONTENT_MALFORMED']
        audit_valid=audit_ok(db,actor.tenant_id)
        try:
            envelope=json_obj(c.approval_envelope_json) if c.approval_envelope_json else None
        except MALFORMED:
            envelope=None
        return {'approval_envelope':envelope,
                'approval_envelope_sha256':c.approval_envelope_hash,
                'content':content,'manifest_sha256':h,'approved_evidence_sha256':c.approved_evidence_hash,
                'matches_approval':verified and audit_valid and c.approved_evidence_hash==h if c.approved_evidence_hash else None,
                'audit_chain_verified':audit_valid,'record_integrity_verified':verified and audit_valid,
                'integrity_issues':issues if audit_valid else ['AUDIT_INTEGRITY_FAILURE'],
                'external_trust_anchor':False,'real_release':False}

    @app.get('/api/audit/verify')
    def audit_verify(actor:User=Depends(get_actor),db:Session=Depends(get_db)):
        require(actor,'AUDITOR')
        t=db.get(Tenant,actor.tenant_id)
        return {'tenant_id':actor.tenant_id,'verified':audit_ok(db,actor.tenant_id),
                'event_count':t.audit_seq,'head_sha256':t.audit_head,
                'externally_anchored':False}

    return app

# Startup in an explicit local demo profile only. Initialization is a CLI step.
app=create_app()
