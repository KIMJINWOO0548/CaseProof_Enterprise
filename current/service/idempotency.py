"""Completed mutation responses, committed atomically with the audited mutation."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from reference.evidence_pack import canonical_json, digest
from .models import IdempotencyRecord


def fingerprint(operation, resource_id, body, expected_revision):
    route='/api/changes' if operation=='create' else '/api/changes/{cid}/'+operation
    return digest({'method':'POST','route':route,'resource_id':resource_id,
                   'body':body,'expected_revision':expected_revision})


def replay(db, actor, key, operation, request_hash):
    # The actor-wide namespace also rejects accidental key reuse across operations.
    record=db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.tenant_id==actor.tenant_id,
        IdempotencyRecord.actor_id==actor.id, IdempotencyRecord.key==key).with_for_update())
    if record is None:
        return None
    if record.operation!=operation or record.fingerprint!=request_hash:
        raise HTTPException(409,detail={'code':'IDEMPOTENCY_CONFLICT',
            'message':'동일한 키로 다른 요청을 보낼 수 없습니다.'})
    body=json.loads(record.response_json)
    body['replayed']=True
    if 'reused' in body:
        body['reused']=True
    return JSONResponse(body,status_code=record.response_status)


def finish(db, actor, key, operation, request_hash, change, body, status):
    body={**body,'replayed':False}
    db.add(IdempotencyRecord(id=str(uuid4()),tenant_id=actor.tenant_id,actor_id=actor.id,
        key=key,operation=operation,fingerprint=request_hash,change_id=change.id,
        response_status=status,response_json=canonical_json(body).decode(),revision=change.revision,
        created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),completed=True))
    db.flush()
    return body
