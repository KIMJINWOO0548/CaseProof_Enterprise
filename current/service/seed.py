"""Demo-only synthetic seed. NEVER load into real insurer systems."""
import hashlib, json, secrets
from pathlib import Path
from sqlalchemy import select
from .models import Tenant, User, PolicyRule

ROOT = Path(__file__).resolve().parents[1]
DEMO_USERS = [
    ('aurora-analyst','AURORA_NONLIFE','분석가 (손보)',['ANALYST']),
    ('aurora-reviewer','AURORA_NONLIFE','현업 검토자 (손보)',['DOMAIN_REVIEWER']),
    ('aurora-approver','AURORA_NONLIFE','릴리스 승인자 (손보)',['RELEASE_APPROVER']),
    ('aurora-auditor','AURORA_NONLIFE','내부감사 (손보)',['AUDITOR']),
    ('horizon-analyst','HORIZON_LIFE','분석가 (생보)',['ANALYST']),
    ('horizon-reviewer','HORIZON_LIFE','현업 검토자 (생보)',['DOMAIN_REVIEWER']),
    ('horizon-approver','HORIZON_LIFE','릴리스 승인자 (생보)',['RELEASE_APPROVER']),
]

def seed_demo(session, token_map=None):
    """Returns fresh tokens; caller prints once. Never commits itself."""
    rules = json.loads((ROOT/'datasets'/'synthetic_rules.json').read_text(encoding='utf-8'))['rules']
    for tid,label in [('AURORA_NONLIFE','가상 오로라손해보험'),('HORIZON_LIFE','가상 호라이즌생명')]:
        if not session.get(Tenant, tid):
            session.add(Tenant(id=tid,name=label))
    session.flush()
    issued = {}
    for uid,tid,label,roles in DEMO_USERS:
        if session.get(User, uid):
            continue
        tok = (token_map or {}).get(uid) or ('cpdemo_'+secrets.token_urlsafe(32))
        session.add(User(id=uid,tenant_id=tid,label=label,roles_json=json.dumps(roles),
                         enabled=True,token_hash=hashlib.sha256(tok.encode()).hexdigest()))
        issued[uid]=tok
    for rule in rules:
        if not session.get(PolicyRule,rule['rule_id']):
            body=json.dumps(rule,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            session.add(PolicyRule(id=rule['rule_id'],tenant_id=rule['tenant'],payload_json=body,
                                   source_sha256=hashlib.sha256(body.encode()).hexdigest()))
    session.flush()
    return issued
