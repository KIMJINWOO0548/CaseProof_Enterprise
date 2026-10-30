"""Runtime DTO checks against frozen target specimens, without claiming HTTP coverage."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry, Resource

from service.api import schemas_v1 as dto
from service.api.errors import DomainError, error_payload
from service.domain.canonical import canonical_bytes
from service.domain.types import ActorContext, CommandContext, CommandResult, json_payload

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
MODELS = {
    **{f"commands.schema.json#/$defs/{name}": name for name in
       ("CreateChange", "RecordEvaluation", "SubmitChange", "Decision", "CreateHeaders", "MutationHeaders")},
    "change-revision.schema.json": "ChangeRevision",
    "decision-note.schema.json": "DecisionNote",
    "evaluation-run.schema.json": "EvaluationRun",
}
EXAMPLES = [item for item in json.loads((CONTRACTS / "examples/index.json").read_text(encoding='utf-8'))['examples']
            if item['schema'] in MODELS]
REGISTRY = Registry().with_resources((path.as_uri(), Resource.from_contents(json.loads(path.read_text(encoding='utf-8'))))
                                     for path in CONTRACTS.glob('*.schema.json'))


def assert_schema(value, ref):
    name, _, fragment = ref.partition('#')
    uri = (CONTRACTS / name).as_uri() + (('#' + fragment) if fragment else '')
    Draft202012Validator({'$ref': uri}, registry=REGISTRY, format_checker=FormatChecker()).validate(value)


def specimen(name):
    return json.loads((CONTRACTS / "examples" / f"{name}.json").read_text(encoding='utf-8'))


@pytest.mark.parametrize("item", EXAMPLES, ids=lambda item: Path(item['file']).stem)
def test_frozen_contract_examples(item):
    model = getattr(dto, MODELS[item['schema']])
    raw = (CONTRACTS / item['file']).read_bytes()
    if item.get('runtime_valid', item['valid']):
        normalized = dto.parse_body(model, raw).model_dump(mode='json', by_alias=True)
        canonical_bytes(normalized)
        assert_schema(normalized, item['schema'])
    else:
        with pytest.raises((ValidationError, ValueError, TypeError)):
            dto.parse_body(model, raw)


def test_defaults_and_offset_normalization_preserve_uncertainty():
    value = dto.CaseContext.model_validate({}).model_dump()
    assert value == dict(contract_date=None, incident_date=None, claim_date=None,
                         consultation_date=None, rider_context_status="UNKNOWN", riders=[], recorded_as_of=None)
    full = dto.RecordEvaluation.model_validate(specimen('evaluation-valid')).model_dump()
    context = full['case_inputs'][0]['case_context']
    assert context['recorded_as_of'] == '2026-10-29T03:34:56.123456Z'
    assert context['rider_context_status'] == 'CONFIRMED' and context['riders'] == []
    created = dto.CreateChange.model_validate(specimen('create-minimal')).model_dump()
    assert created['parent_change_id'] is None and created['parent_relation'] is None


@pytest.mark.parametrize('raw', [b'{"decision":"APPROVE","decision":"REJECT","reason":"Review complete"}',
                                  b'{"decision":"APPROVE","reason":"\xff"}',
                                  b'{"decision":"APPROVE","reason":"Review \\ud800 invalid"}',
                                  b'{"decision":"APPROVE","reason":"Review complete","x":NaN}'])
def test_raw_body_fail_closed(raw):
    with pytest.raises((ValueError, TypeError)):
        dto.parse_body(dto.Decision, raw)


@pytest.mark.parametrize('value', [True, 1.0, '1', -1, 10000])
def test_claim_days_has_no_python_coercion(value):
    body = specimen('evaluation-valid')
    body['case_inputs'][0]['claim_days'] = value
    with pytest.raises(ValidationError):
        dto.RecordEvaluation.model_validate(body)


def test_duplicate_case_ids_and_nested_unknown_fields_rejected():
    body = specimen('evaluation-valid')
    other = copy.deepcopy(body['case_inputs'][0])
    other['claim_days'] += 1
    body['case_inputs'].append(other)
    with pytest.raises(ValidationError):
        dto.RecordEvaluation.model_validate(body)
    body = specimen('evaluation-valid')
    body['case_inputs'][0]['case_context']['answer'] = 'private'
    with pytest.raises(ValidationError):
        dto.RecordEvaluation.model_validate(body)


@pytest.mark.parametrize('date_value', ['2026-02-30', '2026-1-02', '2026-01-02T00:00:00Z', 20260102])
def test_business_date_is_not_a_timestamp(date_value):
    with pytest.raises(ValidationError):
        dto.CaseContext.model_validate({'contract_date': date_value})


def test_rider_interval_and_note_reason_cannot_hide_tampering():
    rider = dict(code='RIDER-1', enrolled_from='2026-01-02', enrolled_to='2026-01-02', confirmation_evidence_id=None)
    with pytest.raises(ValidationError):
        dto.CaseContext.model_validate({'riders': [rider]})
    note = specimen('decision-note-domain')
    note['reason'] = '  Synthetic evidence reviewed.  '
    with pytest.raises(ValidationError):
        dto.DecisionNote.model_validate(note)
    assert dto.Decision.model_validate({'decision': 'APPROVE', 'reason': note['reason']}).reason == note['reason'].strip()


@pytest.mark.parametrize('revision', ['01', '+1', ' 1', '1\n', '١', '9007199254740992', '9'*5000])
def test_revision_header_is_canonical_safe_ascii(revision):
    with pytest.raises(ValidationError):
        dto.MutationHeaders.model_validate({'Idempotency-Key': 'synthetic-key-0001', 'X-Expected-Revision': revision})


def test_extracted_headers_case_insensitive_and_duplicate_names_rejected():
    value = dto.MutationHeaders.model_validate({'idempotency-key': 'synthetic-key-0001', 'x-expected-revision': '2'})
    assert value.revision == 2
    with pytest.raises(ValidationError):
        dto.CreateHeaders.model_validate({'Idempotency-Key': 'synthetic-key-0001', 'idempotency-key': 'synthetic-key-0002'})


def test_contexts_detach_and_freeze_nested_inputs():
    roles = {'ANALYST'}
    actor = ActorContext('tenant-a', 'requester', roles)
    roles.clear()
    assert actor.roles == frozenset({'ANALYST'})
    body = {'riders': [{'code': 'R1'}]}
    context = CommandContext('POST', '/api/v1/changes', 'NEW', 'synthetic-key-0001', None, body)
    result = CommandResult(201, body, 1, False)
    body['riders'][0]['code'] = 'changed'
    assert context.body['riders'][0]['code'] == result.data['riders'][0]['code'] == 'R1'
    with pytest.raises(TypeError):
        context.body['riders'][0]['code'] = 'changed'
    assert canonical_bytes(json_payload(context.body)) == b'{"riders":[{"code":"R1"}]}'


def test_safe_errors_match_contract_without_exception_or_unknown_details():
    error = DomainError('STALE_REVISION', current_revision=3)
    assert error.status_code == 409
    payload = error_payload(error, '00000000-0000-4000-8000-000000000064')
    assert payload['error']['details'] == {'current_revision': 3}
    assert payload['error']['retryable'] is False
    assert_schema(payload, 'error.schema.json')
    with pytest.raises((ValueError, TypeError)):
        DomainError('INTERNAL_ERROR', token='private')
    with pytest.raises((ValueError, TypeError)):
        DomainError('INTERNAL_ERROR', current_revision=3)


@pytest.mark.parametrize('code', ['RETRYABLE_CONFLICT', 'OUTCOME_UNKNOWN', 'INVALID_REQUEST', 'INTERNAL_ERROR'])
def test_error_retryability_and_field_allowlist(code):
    args = {'fields': ['reason', 'reason']} if code == 'INVALID_REQUEST' else {}
    error = DomainError(code, **args)
    payload = error_payload(error, '00000000-0000-4000-8000-000000000064')
    assert_schema(payload, 'error.schema.json')
    assert payload['error']['retryable'] == (code in ('RETRYABLE_CONFLICT', 'OUTCOME_UNKNOWN'))


@pytest.mark.parametrize('value', ['0001-01-01T00:00:00+23:59', '9999-12-31T23:59:59-23:59',
                                  '2026-10-29T12:34:56+00:99', '2026-10-29T12:34:56.1234567Z'])
def test_unrepresentable_or_invalid_timestamp_rejected(value):
    with pytest.raises(ValidationError):
        dto.CaseContext.model_validate({'recorded_as_of': value})


def test_snapshot_requires_explicit_nulls_and_disallows_jobs():
    for field in ('parent_change_id', 'parent_relation', 'assessment_sha256', 'active_job_id'):
        body = specimen('snapshot-genesis')
        del body[field]
        with pytest.raises(ValidationError):
            dto.ChangeRevision.model_validate(body)
    body = specimen('snapshot-genesis')
    body['active_job_id'] = body['change_id']
    with pytest.raises(ValidationError):
        dto.ChangeRevision.model_validate(body)
