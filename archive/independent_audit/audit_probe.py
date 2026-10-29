"""Audit-only, synthetic: execute selected original code with in-memory ORM stubs.
NOT an HTTP, SQLAlchemy or PostgreSQL integration test; no input files are modified.
"""
import ast, copy, json, pathlib, sys, os
from types import SimpleNamespace

ROOT=pathlib.Path(os.environ.get('CASEPROOF_CURRENT', str(pathlib.Path(__file__).resolve().parents[1]/'audit_execution'/'current'))).resolve()
sys.path.insert(0,str(ROOT))
from reference.evidence_pack import digest, canonical_json
from reference.resolver import load_rules, resolve
from reference.paired_benchmark import compare_runs

class Column:
    def __eq__(self, other): return ('eq', self, other)
    def __add__(self, other): return ('add', self, other)
class Model:
    def __init__(self, **kw): self.__dict__.update(kw)
class Tenant(Model): id=Column()
class Change(Model): id=Column(); tenant_id=Column(); revision=Column(); status=Column()
class AuditEvent(Model): tenant_id=Column(); sequence=Column()
class Evaluation(Model): tenant_id=Column(); change_id=Column(); id=Column()
class DecisionNote(Model): tenant_id=Column(); change_id=Column()
class Select:
    def __init__(self, cls): self.cls=cls
    def where(self,*a): return self
    def order_by(self,*a): return self
    def with_for_update(self): return self
    def scalars(self): return self
    def all(self): return list(DBITEMS[self.cls])
    def scalar_one(self): return DBITEMS[self.cls][0]
class DB:
    def get(self,cls,key): return tenant if cls is Tenant and key==tenant.id else None
    def execute(self,q): return q
    def add(self,obj): DBITEMS[type(obj)].append(obj)
    def commit(self): pass
    def rollback(self): pass

ZERO='0'*64
tenant=Tenant(id='SYNTHETIC_A',audit_seq=0,audit_head=ZERO)
c=Change(id='change_synthetic',tenant_id=tenant.id,title='synthetic only',product='P',workflow='W',
         rule_key='K',requester_id='author',owner_id='author',dataset_hash='d'*64,evaluator_hash='e'*64,
         source_hash='s'*64,created_at='2026-01-01',updated_at='2026-01-01',status='PENDING_DOMAIN_REVIEW',
         revision=4,domain_reviewer_id=None,release_approver_id=None,approved_evidence_hash=None)
DBITEMS={Tenant:[tenant],Change:[c],AuditEvent:[],Evaluation:[],DecisionNote:[]}

def add_event(kind, details, actor='author'):
    seq=tenant.audit_seq+1
    body={'actor_id':actor,'at':'2026-01-01','kind':kind,'subject_id':c.id,'details':details}
    env={'sequence':seq,'prev_hash':tenant.audit_head,'event':body}
    h=digest(env)
    DBITEMS[AuditEvent].append(AuditEvent(sequence=seq,prev_hash=tenant.audit_head,event_json=canonical_json(body).decode(),event_hash=h,tenant_id=tenant.id))
    tenant.audit_seq=seq;tenant.audit_head=h
snapshot={k:getattr(c,k) for k in ('tenant_id','title','product','workflow','rule_key','requester_id','owner_id','dataset_hash','evaluator_hash','source_hash','created_at')}
add_event('CHANGE_CREATED',{'snapshot':snapshot})
for i in (1,2):
    request={'case':i}; result={'verdict':'PASS','resolved_rule_id':f'rule{i}'}
    ev=Evaluation(id=f'e{i}',tenant_id=tenant.id,change_id=c.id,actor_id='author',request_json=canonical_json(request).decode(),request_hash=digest(request),result_json=canonical_json(result).decode(),verdict='PASS')
    DBITEMS[Evaluation].append(ev)
    add_event('EVALUATION_RECORDED',{'evaluation_id':ev.id,'request_sha256':ev.request_hash,'result_sha256':digest(result),'verdict':'PASS'})
add_event('SUBMITTED_FOR_DOMAIN_REVIEW',{})

source=(ROOT/'service/app.py').read_text(encoding='utf-8'); tree=ast.parse(source)
selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('audit_ok','record_integrity','require_integrity')]
create=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='create_app')
release=copy.deepcopy(next(x for x in create.body if isinstance(x,ast.FunctionDef) and x.name=='release_review'))
release.decorator_list=[]
release.args.defaults=[]

def err(status,code,message): raise RuntimeError(f'{status} {code}: {message}')
def require(actor,role):
    if role not in actor.roles: err(403,'PERMISSION_DENIED','missing role')
def revision_update(db,change,expected,state,**kwargs):
    if change.revision!=expected: err(409,'STALE_REVISION','stale')
    change.revision+=1;change.status=state
    for k,v in kwargs.items(): setattr(change,k,v)
def append_audit(db,tenant_id,actor_id,kind,obj_id,details): add_event(kind,details,actor_id)
ns={'__builtins__':__builtins__,'Session':object,'Change':Change,'Tenant':Tenant,'AuditEvent':AuditEvent,
    'Evaluation':Evaluation,'DecisionNote':DecisionNote,'select':Select,'json_obj':json.loads,'digest':digest,
    'ZERO':ZERO,'error':err,'require':require,'get_change':lambda db,tid,cid:c,
    'revision_update':revision_update,'append_audit':append_audit,'safe_commit':lambda db:db.commit(),
    'scope_rules':lambda *args: [], 'scope_hash':lambda *args:c.source_hash,
    'DATASET_HASH':c.dataset_hash,'EVALUATOR_HASH':c.evaluator_hash,
    'evidence_content':lambda db,change:{'change_id':change.id,'synthetic':True},
    'utcnow':lambda:'2026-01-01','uuid4':lambda:'synthetic-note-id',
    'hashlib':__import__('hashlib'),'payload':lambda change,db:{'status':change.status,'revision':change.revision}}
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*selected,release],type_ignores=[])
exec(compile(ast.fix_missing_locations(module),str(ROOT/'service/app.py'),'exec'),ns)
db=DB()
print('BASELINE', 'audit_ok=',ns['audit_ok'](db,c.tenant_id),'record_integrity=',ns['record_integrity'](db,c),'notes=',len(DBITEMS[DecisionNote]),'status=',c.status)
# Only the mutable Change row changes; events, chain, evaluations, actors remain intact.
c.status='PENDING_RELEASE'
print('STATE_TAMPER', 'audit_ok=',ns['audit_ok'](db,c.tenant_id),'record_integrity=',ns['record_integrity'](db,c),'domain_notes=',len(DBITEMS[DecisionNote]),'status=',c.status)
req=SimpleNamespace(expected_revision=c.revision,decision='APPROVE',reason='synthetic audit approval reason')
actor=SimpleNamespace(id='different_approver',tenant_id=tenant.id,roles={'RELEASE_APPROVER'})
ret=ns['release_review'](c.id,req,actor,db)
print('EXTRACTED_ROUTE_WITH_ORM_STUBS',ret,'audit_ok=',ns['audit_ok'](db,c.tenant_id),
      'record_integrity=',ns['record_integrity'](db,c),'notes=',[(n.stage,n.decision) for n in DBITEMS[DecisionNote]])
assert ret['status']=='APPROVED_FOR_DEMO' and not any(n.stage=='DOMAIN' for n in DBITEMS[DecisionNote])
assert ns['audit_ok'](db,c.tenant_id) and ns['record_integrity'](db,c)[0]

b={'dataset_hash':'a'*64,'evaluator_hash':'b'*64,'cases':[{'id':'S1','correct':False,'critical':False,'complete':False}]}
candidate=copy.deepcopy(b);candidate['cases'][0].update(correct=True,complete=True)
print('INCOMPLETE_BASELINE',json.dumps(compare_runs(b,candidate),ensure_ascii=False,sort_keys=True))
assert compare_runs(b,candidate)['status']=='ELIGIBLE_FOR_HUMAN_REVIEW'

rules=load_rules(); query={'tenant':'HORIZON_LIFE','product':'LIFE-201','workflow':'LIFE_CLAIM_DOCUMENTS','rule_key':'DOCUMENT_WINDOW_DAYS','contract_start_date':'2026-06-30','rider_codes':['R-PREMIUM'],'as_of_recorded':'2026-10-28T00:00:00+09:00'}
r=copy.deepcopy(rules)
for rule in r:
    if rule['rule_id']=='HZ-LIFE-RIDER-PREMIUM':rule['source_state']='DRAFT'
print('DRAFT_RIDER_OVER_PUBLISHED_BASE',json.dumps(resolve(query,r).as_json(),ensure_ascii=False,sort_keys=True))
assert resolve(query,r).status=='RESOLVED'
# Exercise the original new_change function twice with a synthetic in-memory stub.
create_route=copy.deepcopy(next(x for x in create.body if isinstance(x,ast.FunctionDef) and x.name=='new_change'))
create_route.decorator_list=[]
create_route.args.defaults=[]
ids=iter(['synthetic-change-1','synthetic-change-2'])
create_ns={**ns,'uuid4':lambda:next(ids),'scope_rules':lambda *args: ['synthetic-scope'],
           'append_audit':lambda *args:None,
           'payload':lambda change,db:{'id':change.id,'status':change.status}}
create_module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),create_route],type_ignores=[])
exec(compile(ast.fix_missing_locations(create_module),str(ROOT/'service/app.py'),'exec'),create_ns)
request=SimpleNamespace(title='synthetic change',product='P',workflow='W',rule_key='K',
                        dataset_hash=c.dataset_hash,evaluator_hash=c.evaluator_hash,source_hash=c.source_hash)
analyst=SimpleNamespace(id='author',tenant_id=tenant.id,roles={'ANALYST'})
first=create_ns['new_change'](request,analyst,db)
second=create_ns['new_change'](request,analyst,db)
print('REPLAY_SAME_CREATE',first,second,'unique_ids=',first['id']!=second['id'])
assert first['id']!=second['id']
print('PASS: reproductions executed against extracted function bodies/reference code; fake ORM stubs are not a full integration test')
