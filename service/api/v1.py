"""Explicitly mounted v1 HTTP boundary; the baseline application stays separate."""
from uuid import uuid4
from fastapi import APIRouter, Request, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter
from sqlalchemy import select

from service import models_v1 as m
from service.api.errors import DomainError, error_payload
from service.api.schemas_v1 import CreateHeaders, MutationHeaders, UUIDv4, parse_body
from service.auth import current_actor
from service.commands import BASE, ROUTES, authorize, execute_command, normalize
from service.domain.types import CommandContext, json_payload
from service.idempotency_v1 import lookup, replay
from service.repositories import decode, get_change, load_history, require


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


def build_router(session_factory, authenticator):
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
                body = parse_body(model, await request.body()).model_dump()
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
                except DomainError:
                    data.update(historical_integrity='INVALID', latest_run=None)
                return JSONResponse({'data': data})
        return await respond(request, action)

    @router.get('/changes/{change_id}/evidence')
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
                except DomainError:
                    data = {'historical_integrity': 'INVALID', 'current_approval_eligibility': 'BLOCKED',
                            'external_anchor': 'NOT_CONFIGURED', 'approved_revision': None, 'envelope_sha256': None}
                return JSONResponse({'data': data})
        return await respond(request, action)

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
