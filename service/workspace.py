"""Explicit synthetic v1 workspace profile; never initializes data at startup."""
from copy import deepcopy
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from service import models_v1 as m
from service.api.errors import DomainError, error_payload
from service.api.v1 import build_router
from service.auth import DemoTokenAuthenticator, current_actor
from service.domain.canonical import canonical_bytes
from service.repositories import ZERO, add_payload, decode, load_history, require

ROOT = Path(__file__).resolve().parents[1]
ACTORS = {'analyst': 'ANALYST', 'reviewer': 'DOMAIN_REVIEWER',
          'approver': 'RELEASE_APPROVER', 'auditor': 'AUDITOR'}


def seed_workspace(db, tenant_id='fictional'):
    """Seed one new tenant in a caller-owned transaction, without tokens or decisions."""
    if db.get(m.Tenant, tenant_id) is not None:
        raise ValueError('Refusing to overwrite an existing workspace tenant')
    db.add(m.Tenant(id=tenant_id))
    db.flush()
    db.add(m.TenantAuditHead(tenant_id=tenant_id, sequence=0, head_sha256=ZERO))
    for name, role in ACTORS.items():
        db.add(m.Actor(tenant_id=tenant_id, id=name, enabled=True,
                       roles_payload=canonical_bytes([role])))
    db.flush()
    presets = []
    for name in ('harbor', 'orchard', 'lantern'):
        pack = deepcopy(json.loads((ROOT / 'datasets' / 'packs' / ('fictional_' + name + '.json')).read_text(encoding='utf-8')))
        pack['tenant_id'] = tenant_id
        ids = {key: str(uuid4()) for key in ('candidate', 'bundle', 'dataset', 'suite', 'evaluator', 'adapter', 'policy', 'eligibility')}
        rule = pack['rules'][0]
        label = name.capitalize() + ' · fictional synthetic fixture'
        body = dict(title=label, pack_version_id=pack['pack_id'], product_id=rule['product_id'],
                    workflow=rule['workflow'], rule_key=rule['rule_key'], candidate_snapshot_id=ids['candidate'],
                    source_bundle_id=ids['bundle'], dataset_version_id=ids['dataset'],
                    suite_version_id=ids['suite'], evaluator_version_id=ids['evaluator'])
        case_inputs = [dict(case_id=name + '-base', claim_days=rule['value'], case_context=dict(
            contract_date='2025-02-01', incident_date='2025-02-02', claim_date='2025-02-03',
            consultation_date='2025-02-03', rider_context_status='CONFIRMED', riders=[],
            recorded_as_of='2025-03-01T00:00:00.000000Z'))]
        preset = dict(id=name, label=label, create_body=body, case_inputs=case_inputs, pack_id=pack['pack_id'])
        policy = add_payload(db, m.PolicySnapshot, dict(schema='policy_v1', tenant_id=tenant_id,
                                                       id=ids['policy'], pack_snapshot=pack))
        members, source_refs = [], []
        for source in pack['sources']:
            matching = next(r for r in pack['rules'] if r['source_id'] == source['source_id'])
            row = add_payload(db, m.SourceSnapshot, dict(schema='source_v1', tenant_id=tenant_id,
                id=str(uuid4()), source_id=source['source_id'], policy_version_id=source['policy_version'],
                value=matching['value'], status='APPROVED', synthetic=True))
            members.append(dict(source_id=row.id, policy_id=policy.id,
                                source_sha256=row.payload_sha256, policy_sha256=policy.payload_sha256))
            source_refs.append(dict(id=row.id, payload_sha256=row.payload_sha256,
                                    policy_version_id=source['policy_version'], status='APPROVED'))
        versions = sorted({s['policy_version'] for s in pack['sources']})
        payloads = [(m.AdapterSnapshot, 'adapter', dict(kind='fake-deterministic')),
            (m.CandidateSnapshot, 'candidate', dict(model_id=None, prompt_id=None, adapter_version_id=ids['adapter'])),
            (m.SourceBundle, 'bundle', dict(members=sorted(members, key=lambda member: member['source_id']))),
            (m.DatasetSnapshot, 'dataset', dict(synthetic=True)), (m.EvaluatorSnapshot, 'evaluator', dict(synthetic=True)),
            (m.SuiteSnapshot, 'suite', dict(required_case_ids=[c['case_id'] for c in case_inputs],
                # These versioned fictional fixtures each contain one source policy.
                minimum_distinct_policy_versions=1, required_coverage_labels=[],
                case_policy_versions={c['case_id']: versions for c in case_inputs},
                coverage_by_case={c['case_id']: [] for c in case_inputs}, workspace=preset))]
        for model, key, extra in payloads:
            add_payload(db, model, dict(schema=key + '_v1', tenant_id=tenant_id, id=ids[key], **extra))
        for member in members:
            db.add(m.SourceBundleMember(tenant_id=tenant_id, source_bundle_id=ids['bundle'],
                                        source_id=member['source_id'], policy_id=member['policy_id']))
        add_payload(db, m.SourceEligibilitySnapshot, dict(schema='source_eligibility_v1', tenant_id=tenant_id,
            id=ids['eligibility'], source_bundle_id=ids['bundle'], sequence=1, eligible=True,
            source_refs=sorted(source_refs, key=lambda source: source['id']), policy_version_id='synthetic-eligibility-v1'))
        presets.append(preset)
    return {'presets': presets}


def create_workspace_app(session_factory, registry):
    if os.environ.get('CASEPROOF_DEMO_MODE') != '1':
        raise RuntimeError('CASEPROOF_DEMO_MODE=1 is required for the synthetic v1 workspace')
    authenticator = DemoTokenAuthenticator(registry)
    app = FastAPI(title='CaseProof synthetic v1 workspace')
    app.include_router(build_router(session_factory, authenticator))

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(error_payload(error, str(uuid4())), status_code=error.status_code)

    @app.middleware('http')
    async def private_response(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def actor_for(request, db):
        auth = request.headers.get('authorization', '')
        require(auth.startswith('Bearer ') and bool(auth[7:]) and ' ' not in auth[7:], 'UNAUTHENTICATED')
        require(not request.query_params, 'INVALID_REQUEST')
        actor = current_actor(db, authenticator(auth[7:], db))
        require(bool(actor.roles), 'FORBIDDEN')
        return actor

    @app.get('/api/v1/workspace', dependencies=[Depends(HTTPBearer(auto_error=False))])
    async def workspace(request: Request):
        with session_factory() as db, db.begin():
            actor = actor_for(request, db)
            suites = db.execute(select(m.SuiteSnapshot).where(m.SuiteSnapshot.tenant_id == actor.tenant_id)).scalars()
            presets = [data['workspace'] for row in suites if 'workspace' in (data := decode(row))]
            order = {'harbor': 0, 'orchard': 1, 'lantern': 2}
            presets.sort(key=lambda preset: (order.get(preset['pack_id'], 3), preset['id']))
            return {'data': {'actor': {'tenant_id': actor.tenant_id, 'actor_id': actor.actor_id,
                'roles': sorted(actor.roles)}, 'presets': presets,
                'capabilities': {'external_model': False, 'external_anchor': False, 'synthetic': True}}}

    @app.get('/api/v1/changes', dependencies=[Depends(HTTPBearer(auto_error=False))])
    async def changes(request: Request):
        with session_factory() as db, db.begin():
            actor = actor_for(request, db)
            changes = db.execute(select(m.Change).where(m.Change.tenant_id == actor.tenant_id)
                                 .order_by(m.Change.id).limit(200)).scalars()
            results = []
            for change in changes:
                try:
                    results.append(load_history(db, actor.tenant_id, change.id)['snapshot'])
                except DomainError:
                    results.append(dict(change_id=change.id, tenant_id=actor.tenant_id, title='기록 무결성 오류',
                        pack_version_id='—', revision=change.revision, status='INTEGRITY_INVALID'))
            return {'data': results}

    app.mount('/static', StaticFiles(directory=ROOT / 'service' / 'static'), name='static')

    @app.get('/', include_in_schema=False)
    @app.get('/v1', include_in_schema=False)
    async def index():
        return FileResponse(ROOT / 'service' / 'static' / 'v1.html')

    return app
