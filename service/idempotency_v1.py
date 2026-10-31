"""Actor-scoped committed results; helpers never commit."""
from sqlalchemy import select
from service.api.errors import DomainError
from service.domain.canonical import content_hash
from service.domain.types import CommandResult, json_payload
from service.models_v1 import IdempotencyRecord


def fingerprint(command):
    return content_hash('request', {'schema': 'mutation_fingerprint_v1', 'method': command.method.upper(),
        'route_template': command.route_template, 'resource_id': command.resource_id,
        'body': json_payload(command.body), 'expected_revision': command.expected_revision})


def lookup(db, actor, key):
    return db.execute(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id == actor.tenant_id,
        IdempotencyRecord.actor_id == actor.actor_id, IdempotencyRecord.key == key)).scalar_one_or_none()


def replay(row, command=None):
    from service.repositories import decode
    data = decode(row, 'idempotency')
    if command is not None and row.fingerprint_sha256 != fingerprint(command):
        raise DomainError('IDEMPOTENCY_CONFLICT')
    if data['request_sha256'] != row.fingerprint_sha256 or data['response_status'] != row.original_status or data['result_revision'] != row.result_revision:
        raise DomainError('EVIDENCE_RECORD_TAMPERED')
    return CommandResult(data['response_status'], data['response_data_json'], data['result_revision'], True)
