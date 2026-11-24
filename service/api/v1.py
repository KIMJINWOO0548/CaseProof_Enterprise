"""Explicitly mounted v1 HTTP boundary; the baseline application stays separate."""
import re
from uuid import uuid4
from fastapi import APIRouter, Request, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter
from sqlalchemy import select

from service import models_v1 as m
from service.api.errors import DomainError, error_payload
from service.api.schemas_v1 import CSVPreview, CreateHeaders, MAX_REVISION, MutationHeaders, UUIDv4, parse_body
from service.auth import current_actor
from service.commands import BASE, ROUTES, authorize, execute_command, normalize
from service.domain.canonical import content_hash
from service.domain.types import CommandContext, json_payload
from service.idempotency_v1 import lookup, replay
from service.repositories import decode, get_change, load_history, require
from service.evaluation.csv_preview import CSV_LIMIT, preview_cases
from service.evaluation.run_comparison import compare_runs, summarize_history
from service.review import read_review


REQUEST_CONTEXT_HEADER = 'X-CaseProof-Request-Context'


def _headers(request, create):
    extracted = {}
    for raw_name, raw_value in request.scope['headers']:
        name = raw_name.decode('latin-1').lower()
        if name in ('idempotency-key', 'x-expected-revision'):
            if name in extracted:
                raise DomainError('INVALID_REQUEST')
            extracted[name] = raw_value.decode('latin-1')
    return (CreateHeaders if create else MutationHeaders).model_validate(extracted)


def _identity(value):
    return TypeAdapter(UUIDv4).validate_python(value, strict=True)


def _schema(model):
    schema = model.model_json_schema()
    definitions = schema.pop('$defs', {})
    def inline(value):
        if isinstance(value, list):
            return [inline(item) for item in value]
        if isinstance(value, dict):
            if '$ref' in value:
                return inline(definitions[value['$ref'].split('/')[-1]])
            return {key: inline(item) for key, item in value.items()}
        return value
    return inline(schema)


def _immutable_refs(history):
    """Project validated history into identities and purpose-separated hashes only."""
    def ref(purpose, payload):
        return {'id': payload['id'], 'payload_sha256': content_hash(purpose, payload)} if payload is not None else None

    stored = history['refs']
    result = {}
    for target, name, purpose in (
        ('candidate_snapshot_ref', 'candidate_snapshot', 'candidate'), ('source_bundle_ref', 'source_bundle', 'source-bundle'),
        ('dataset_ref', 'dataset', 'dataset'), ('suite_ref', 'suite', 'suite'), ('evaluator_ref', 'evaluator', 'evaluator'),
        ('model_ref', 'model', 'model'), ('prompt_ref', 'prompt', 'prompt'),
    ):
        result[target] = ref(purpose, stored[name])
    for target, purpose, payloads in (
        ('run_refs', 'evaluation-run', history['runs']), ('decision_refs', 'decision', history['decisions']),
        ('transition_refs', 'transition', history['transitions']), ('audit_event_refs', 'audit-event', history['events']),
        ('source_refs', 'source', stored['sources']), ('policy_refs', 'policy', stored['policies']),
        ('source_eligibility_refs', 'source-eligibility', stored['source_eligibility']),
    ):
        result[target] = [ref(purpose, payload) for payload in payloads]
    adapter_ids = {stored['candidate_snapshot'].get('adapter_version_id')} | {run['adapter_version_id'] for run in history['runs']}
    result['adapter_refs'] = [ref('adapter', adapter) for adapter in stored['adapters'] if adapter['id'] in adapter_ids]
    result['change_revision_refs'] = [
        {'change_id': snapshot['change_id'], 'revision': snapshot['revision'],
         'payload_sha256': content_hash('change-revision', snapshot)} for snapshot in history['snapshots']]
    for target, name, purpose in (('assessment_ref', 'assessment', 'assessment'),
                                  ('approval_envelope_ref', 'envelope', 'approval-envelope')):
        payload = history[name]
        result[target] = {'change_id': payload['change_id'], 'payload_sha256': content_hash(purpose, payload)} if payload else None
    return result


def build_router(session_factory, authenticator, *, request_context=None):
    router = APIRouter(prefix='/api/v1', dependencies=[Depends(HTTPBearer(auto_error=False))])

    def actor_for(request):
        auth = request.headers.get('authorization', '')
        require(auth.startswith('Bearer ') and bool(auth[7:]) and ' ' not in auth[7:], 'UNAUTHENTICATED')
        with session_factory() as db, db.begin():
            return authenticator(auth[7:], db)

    async def respond(request, action):
        request_id = str(uuid4())
        try:
            return await action()
        except DomainError as error:
            return JSONResponse(error_payload(error, request_id), status_code=error.status_code,
                headers={'Retry-After': '1'} if error.status_code == 503 else {})
        except (ValueError, TypeError, UnicodeError):
            error = DomainError('INVALID_REQUEST')
            return JSONResponse(error_payload(error, request_id), status_code=422)
        except Exception:
            error = DomainError('INTERNAL_ERROR')
            return JSONResponse(error_payload(error, request_id), status_code=500)

    def mutation(route, model):
        async def endpoint(request: Request):
            async def action():
                actor = actor_for(request)
                require(not request.query_params, 'INVALID_REQUEST')
                headers = _headers(request, route == BASE)
                raw_body = await request.body()
                context_headers = request.headers.getlist(REQUEST_CONTEXT_HEADER)
                if context_headers:
                    require(len(context_headers) == 1, 'INVALID_REQUEST')
                    expected_context = request_context(actor) if request_context is not None else None
                    require(expected_context == context_headers[0], 'REQUEST_CONTEXT_CHANGED')
                body = parse_body(model, raw_body).model_dump()
                identity = 'NEW' if route == BASE else _identity(request.path_params['change_id'])
                command = CommandContext('POST', route, identity, headers.key,
                    None if route == BASE else headers.revision, body)
                result = execute_command(session_factory, actor, command)
                return JSONResponse({'data': json_payload(result.data), 'result_revision': result.result_revision,
                                     'replayed': result.replayed}, status_code=result.status_code)
            return await respond(request, action)
        endpoint.__name__ = 'v1_' + route.rsplit('/', 1)[-1].replace('-', '_')
        return endpoint

    for route, (_, model) in ROUTES.items():
        header_model = CreateHeaders if route == BASE else MutationHeaders
        parameters = [{'in': 'header', 'name': name, 'required': True, 'schema': field}
                      for name, field in header_model.model_json_schema()['properties'].items()]
        if request_context is not None:
            parameters.append({'in': 'header', 'name': REQUEST_CONTEXT_HEADER, 'required': False,
                               'schema': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                               'description': 'Original browser request context from the authenticated workspace.'})
        router.add_api_route(route.removeprefix('/api/v1'), mutation(route, model), methods=['POST'],
            openapi_extra={'parameters': parameters, 'requestBody': {'required': True, 'content': {'application/json': {'schema': _schema(model)}}},
                'responses': {str(code): {'description': description} for code, description in
                    [(201 if route == BASE or route.endswith('evaluation-runs') else 200, 'Committed result or historical replay'),
                     (401, 'Unauthenticated'), (403, 'Forbidden'), (404, 'Not found'), (409, 'Conflict'), (422, 'Invalid request'), (503, 'Retry same key')]}})

    @router.get('/changes/{change_id}')
    async def current(change_id: str, request: Request):
        async def action():
            actor = actor_for(request)
            _identity(change_id)
            with session_factory() as db, db.begin():
                actor = current_actor(db, actor)
                require(bool(actor.roles), 'FORBIDDEN')
                change = get_change(db, actor.tenant_id, change_id)
                data = {column.name: getattr(change, column.name) for column in change.__table__.columns}
                try:
                    history = load_history(db, actor.tenant_id, change_id)
                    data.update(snapshot=history['snapshot'], latest_run=history['runs'][-1] if history['runs'] else None,
                                historical_integrity='VALID')
                except DomainError as error:
                    integrity = 'LEGACY_UNVERIFIED' if error.code == 'EXECUTION_CONFIG_UNVERIFIED' else 'INVALID'
                    data.update(historical_integrity=integrity, latest_run=None)
                return JSONResponse({'data': data})
        return await respond(request, action)

    def run_history(db, actor, change_id):
        actor = current_actor(db, actor)
        require(bool(actor.roles), 'FORBIDDEN')
        get_change(db, actor.tenant_id, change_id)
        # Validate all runs, immutable references and the ledger before slicing.
        return load_history(db, actor.tenant_id, change_id)

    @router.get('/changes/{change_id}/evaluation-runs', description=(
        'Read-only saved v2 run summaries, newest revision first, latest 100 after full history validation. '
        'Payload hashes refer to the original evaluation-run payload. No query parameters.'))
    async def evaluation_runs(change_id: str, request: Request):
        async def action():
            actor = actor_for(request)
            _identity(change_id)
            require(not request.query_params, 'INVALID_REQUEST')
            with session_factory() as db, db.begin():
                history = run_history(db, actor, change_id)
                return JSONResponse({'data': summarize_history(history['runs'])})
        return await respond(request, action)

    @router.post('/changes/{change_id}/evaluation-runs/preview-csv',
        description='Validate synthetic CSV against the saved suite. Does not execute or persist evaluations.',
        openapi_extra={
            'parameters': [
                {'in': 'header', 'name': 'X-Expected-Revision', 'required': True,
                 'schema': MutationHeaders.model_json_schema()['properties']['X-Expected-Revision']},
                {'in': 'header', 'name': REQUEST_CONTEXT_HEADER, 'schema': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}},
            ],
            'requestBody': {'required': True, 'content': {'text/csv': {'schema': {'type': 'string', 'maxLength': CSV_LIMIT}}}},
            'responses': {
                '200': {'description': 'Ready to submit or structured CSV diagnostics',
                        'content': {'application/json': {'schema': {'type': 'object', 'required': ['data'],
                                                                   'properties': {'data': _schema(CSVPreview)}}}}},
                **{str(status): {'description': description} for status, description in
                   [(401, 'Unauthenticated'), (403, 'Forbidden'), (404, 'Not found'), (409, 'Conflict'),
                    (413, 'CSV too large'), (415, 'Unsupported media type'), (422, 'Invalid request')]},
            },
        })
    async def evaluation_csv_preview(change_id: str, request: Request):
        async def action():
            from service.evaluation.runner import suite_cases

            actor = actor_for(request)
            _identity(change_id)
            require(not request.query_params and not request.headers.getlist('idempotency-key'), 'INVALID_REQUEST')
            revisions = request.headers.getlist('x-expected-revision')
            require(len(revisions) == 1 and re.fullmatch(r'[1-9][0-9]{0,15}', revisions[0]), 'INVALID_REQUEST')
            expected_revision = int(revisions[0])
            require(expected_revision <= MAX_REVISION, 'INVALID_REQUEST')
            contexts = request.headers.getlist(REQUEST_CONTEXT_HEADER)
            if contexts:
                require(len(contexts) == 1, 'INVALID_REQUEST')
                require(request_context is not None and request_context(actor) == contexts[0], 'REQUEST_CONTEXT_CHANGED')
            media = request.headers.getlist('content-type')
            require(len(media) == 1 and re.fullmatch(r'text/csv(?:\s*;\s*charset=(?:utf-8|"utf-8"))?', media[0], re.I),
                    'UNSUPPORTED_MEDIA_TYPE')
            body = bytearray()
            async for chunk in request.stream():
                require(len(body) + len(chunk) <= CSV_LIMIT, 'CSV_TOO_LARGE')
                body.extend(chunk)
            with session_factory() as db, db.begin():
                actor = current_actor(db, actor)
                change = get_change(db, actor.tenant_id, change_id)
                authorize(actor, 'EVALUATION_RECORDED', change)
                history = load_history(db, actor.tenant_id, change_id)
                snapshot = history['snapshot']
                require(snapshot['status'] == 'DRAFT', 'INVALID_STATUS')
                revision = snapshot['revision']
                if expected_revision != revision:
                    raise DomainError('STALE_REVISION', current_revision=revision)
                suite_version_id = snapshot['suite_version_id']
                required = suite_cases(history, suite_version_id)
            preview = preview_cases(body, required, suite_version_id, revision)
            data = preview.model_dump()
            for error in data['errors']:
                if error['case_id'] is None:
                    del error['case_id']
            return JSONResponse({'data': data}, headers={'Cache-Control': 'no-store'})
        return await respond(request, action)

    @router.get('/changes/{change_id}/evaluation-runs/{run_id}/coverage')
    async def evaluation_coverage(change_id: str, run_id: str, request: Request):
        async def action():
            from service.evaluation.coverage import read_coverage
            actor = actor_for(request)
            _identity(change_id)
            _identity(run_id)
            require(not request.query_params, 'INVALID_REQUEST')
            with session_factory() as db, db.begin():
                history = run_history(db, actor, change_id)
                run = next((r for r in history['runs'] if r['id'] == run_id), None)
                require(run is not None, 'NOT_FOUND')
                return JSONResponse({'data': read_coverage(db, run)})
        return await respond(request, action)

    @router.get('/changes/{change_id}/evaluation-runs/compare', description=(
        'Read-only descriptive comparison of two UUIDv4 run IDs from the fully validated authorized change. '
        'Exactly baseline_run_id and candidate_run_id, once each. At most 1000 union cases. '
        'Per-dimension counts overlap; any_changed counts union rows. No model-quality verdict.'),
        openapi_extra={'parameters': [dict(name=name, **{'in': 'query'}, required=True,
            schema=TypeAdapter(UUIDv4).json_schema()) for name in ('baseline_run_id', 'candidate_run_id')]})
    async def evaluation_comparison(change_id: str, request: Request):
        async def action():
            actor = actor_for(request)
            _identity(change_id)
            query = request.query_params.multi_items()
            require(len(query) == 2 and {key for key, value in query} == {'baseline_run_id', 'candidate_run_id'}, 'INVALID_REQUEST')
            identities = {key: _identity(value) for key, value in query}
            with session_factory() as db, db.begin():
                history = run_history(db, actor, change_id)
                runs = {run['id']: run for run in history['runs']}
                require(all(identity in runs for identity in identities.values()), 'NOT_FOUND')
                return JSONResponse({'data': compare_runs(runs[identities['baseline_run_id']], runs[identities['candidate_run_id']])})
        return await respond(request, action)

    @router.get('/changes/{change_id}/evidence', description=(
        'Returns integrity diagnostics and immutable_refs containing only canonical identities and purpose-separated '
        'payload_sha256 hashes for the selected change. immutable_refs is null when historical integrity is INVALID '
        'or LEGACY_UNVERIFIED. The legacy current_approval_eligibility field reports source eligibility only; '
        'ELIGIBLE does not authorize approval. Evaluation gates, workflow state and role separation remain independent checks.'))
    async def evidence(change_id: str, request: Request):
        async def action():
            actor = actor_for(request)
            _identity(change_id)
            with session_factory() as db, db.begin():
                actor = current_actor(db, actor)
                require(bool(actor.roles), 'FORBIDDEN')
                get_change(db, actor.tenant_id, change_id)
                try:
                    history = load_history(db, actor.tenant_id, change_id)
                    from service.domain.evidence import verify_evidence
                    data = verify_evidence(history)
                    data['immutable_refs'] = _immutable_refs(history) if data['historical_integrity'] == 'VALID' else None
                except DomainError as error:
                    integrity = 'LEGACY_UNVERIFIED' if error.code == 'EXECUTION_CONFIG_UNVERIFIED' else 'INVALID'
                    data = {'historical_integrity': integrity, 'current_approval_eligibility': 'BLOCKED',
                            'external_anchor': 'NOT_CONFIGURED', 'approved_revision': None, 'envelope_sha256': None,
                            'immutable_refs': None}
                return JSONResponse({'data': data})
        return await respond(request, action)

    @router.get('/changes/{change_id}/review', description=(
        'Read-only review readiness for the current actor and revision, recorded evaluation and current gate '
        'diagnostics, decision notes, and approval-time seal references when verified. Invalid or legacy records '
        'have no evaluation, notes or seal. Mutation requests still recheck authority and the expected revision.'))
    async def review(change_id: str, request: Request):
        async def action():
            actor = actor_for(request)
            _identity(change_id)
            require(not request.query_params, 'INVALID_REQUEST')
            with session_factory() as db, db.begin():
                actor = current_actor(db, actor)
                require(bool(actor.roles), 'FORBIDDEN')
                return JSONResponse({'data': read_review(db, actor, change_id)})
        response = await respond(request, action)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @router.get('/mutations/{key}')
    async def mutation_result(key: str, request: Request):
        async def action():
            actor = actor_for(request)
            CreateHeaders.model_validate({'Idempotency-Key': key})
            with session_factory() as db, db.begin():
                actor = current_actor(db, actor)
                row = lookup(db, actor, key)
                require(row is not None, 'NOT_FOUND')
                payload = decode(row, 'idempotency')
                change = get_change(db, actor.tenant_id, row.change_id)
                route = payload['route_template']
                kind = ROUTES[route][0]
                if kind in ('DOMAIN', 'RELEASE'):
                    kind = kind + '_REJECT'
                authorize(actor, kind, None if kind == 'CHANGE_CREATED' else change)
                result = replay(row)
                return JSONResponse({'data': json_payload(result.data), 'result_revision': result.result_revision,
                                     'replayed': True, 'original_status': result.status_code})
        return await respond(request, action)
    return router
