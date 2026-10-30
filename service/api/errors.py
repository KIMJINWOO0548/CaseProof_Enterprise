"""Safe target errors; request IDs come from the caller, never from exception text."""
from pydantic import TypeAdapter

from service.api.schemas_v1 import MAX_REVISION, UUIDv4

STATUS = {
    'UNAUTHENTICATED': 401, 'FORBIDDEN': 403, 'REQUESTER_ONLY': 403, 'SEPARATION_OF_DUTIES': 403,
    'NOT_FOUND': 404, 'IDEMPOTENCY_CONFLICT': 409, 'AUDIT_INTEGRITY_FAILURE': 409,
    'EVIDENCE_RECORD_TAMPERED': 409, 'INVALID_STATUS': 409, 'STALE_REVISION': 409,
    'EVALUATION_INCOMPLETE': 409, 'RELEASE_GATE_BLOCKED': 409, 'SOURCE_NOT_ELIGIBLE': 409,
    'SNAPSHOT_MISMATCH': 409, 'INVALID_REQUEST': 422, 'RETRYABLE_CONFLICT': 503,
    'OUTCOME_UNKNOWN': 503, 'INTERNAL_ERROR': 500,
}
FIELDS = frozenset(('Idempotency-Key', 'X-Expected-Revision', 'candidate_snapshot_id', 'case_context',
                   'case_id', 'case_inputs', 'claim_days', 'dataset_version_id', 'decision',
                   'evaluator_version_id', 'pack_version_id', 'parent_change_id', 'parent_relation',
                   'product_id', 'reason', 'rule_key', 'source_bundle_id', 'suite_version_id', 'title', 'workflow'))


class DomainError(ValueError):
    def __init__(self, code: str, **details):
        if code not in STATUS:
            raise ValueError('unknown error code')
        permitted = {'current_revision'} if code == 'STALE_REVISION' else {'fields'} if code == 'INVALID_REQUEST' else set()
        if details.keys() - permitted:
            raise ValueError('unsafe error details')
        revision = details.get('current_revision')
        if 'current_revision' in details and (type(revision) is not int or not 1 <= revision <= MAX_REVISION):
            raise ValueError('invalid current revision')
        fields = details.get('fields')
        if 'fields' in details and (type(fields) is not list or any(type(field) is not str or field not in FIELDS for field in fields)):
            raise ValueError('invalid public field name')
        self.code, self.status_code = code, STATUS[code]
        self.details = {'fields': sorted(set(fields))} if fields is not None else dict(details)
        super().__init__(code)


def error_payload(error: DomainError, request_id: str) -> dict:
    TypeAdapter(UUIDv4).validate_python(request_id, strict=True)
    # Revalidate to prevent callers mutating details into an information disclosure.
    safe = DomainError(error.code, **error.details)
    return {'error': {'code': safe.code, 'message': safe.code.replace('_', ' ').capitalize() + '.',
                      'retryable': safe.code in ('RETRYABLE_CONFLICT', 'OUTCOME_UNKNOWN'),
                      'request_id': request_id, 'details': safe.details}}
