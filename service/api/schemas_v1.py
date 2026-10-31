"""Strict target DTOs. Parsing these types does not register an HTTP endpoint."""
import re
from datetime import date, datetime, timezone
from typing import Annotated, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from service.domain.canonical import canonical_bytes, parse_json

MAX_REVISION = 9_007_199_254_740_991
RegisteredId = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\z')]
UUIDv4 = Annotated[str, Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z')]
SHA256 = Annotated[str, Field(pattern=r'^[0-9a-f]{64}\z')]
Revision = Annotated[int, Field(strict=True, ge=1, le=MAX_REVISION)]
ParentRelation = Literal['CORRECTS_REJECTED', 'REPLACES_DRAFT', 'FOLLOWS_APPROVED']
Status = Literal['DRAFT', 'PENDING_DOMAIN_REVIEW', 'PENDING_RELEASE', 'REJECTED', 'APPROVED_FOR_DEMO']


def business_date(value: str) -> str:
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('invalid business date')
    date.fromisoformat(value)
    return value


def normalize_timestamp(value: str) -> str:
    # Sub-microsecond input cannot be represented by this protocol without losing information.
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})', value):
        raise ValueError('invalid offset timestamp')
    offset = re.search(r'[+-]([0-9]{2}):([0-9]{2})\Z', value)
    if offset and (int(offset[1]) > 23 or int(offset[2]) > 59):
        raise ValueError('invalid timezone offset')
    try:
        instant = datetime.fromisoformat(value.upper().replace('Z', '+00:00')).astimezone(timezone.utc)
    except OverflowError as exc:
        raise ValueError('UTC timestamp outside supported range') from exc
    return instant.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def utc_timestamp(value: str) -> str:
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z', value):
        raise ValueError('stored timestamp must be canonical UTC')
    normalize_timestamp(value)
    return value


BusinessDate = Annotated[str, AfterValidator(business_date)]
InputTimestamp = Annotated[str, AfterValidator(normalize_timestamp)]
UTCTimestamp = Annotated[str, AfterValidator(utc_timestamp)]


class JSONModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)

    @model_validator(mode='before')
    @classmethod
    def json_values_only(cls, value):
        if isinstance(value, dict):
            try:
                canonical_bytes(value)
            except TypeError as exc:
                raise ValueError('unsupported JSON value') from exc
        return value


class Rider(JSONModel):
    code: RegisteredId
    enrolled_from: BusinessDate | None
    enrolled_to: BusinessDate | None
    confirmation_evidence_id: UUIDv4 | None

    @model_validator(mode='after')
    def interval(self):
        if self.enrolled_from and self.enrolled_to and self.enrolled_from >= self.enrolled_to:
            raise ValueError('rider interval must be increasing')
        return self


class CaseContext(JSONModel):
    contract_date: BusinessDate | None = None
    incident_date: BusinessDate | None = None
    claim_date: BusinessDate | None = None
    consultation_date: BusinessDate | None = None
    rider_context_status: Literal['CONFIRMED', 'UNKNOWN'] = 'UNKNOWN'
    riders: list[Rider] = Field(default_factory=list)
    recorded_as_of: InputTimestamp | None = None


class CreateChange(JSONModel):
    title: str
    pack_version_id: RegisteredId
    product_id: RegisteredId
    workflow: RegisteredId
    rule_key: RegisteredId
    candidate_snapshot_id: UUIDv4
    source_bundle_id: UUIDv4
    dataset_version_id: UUIDv4
    suite_version_id: UUIDv4
    evaluator_version_id: UUIDv4
    parent_change_id: UUIDv4 | None = None
    parent_relation: ParentRelation | None = None

    @model_validator(mode='after')
    def paired_parent(self):
        if (self.parent_change_id is None) != (self.parent_relation is None):
            raise ValueError('parent fields must be paired')
        return self


class CaseInput(JSONModel):
    case_id: RegisteredId
    claim_days: Annotated[int, Field(strict=True, ge=0, le=9999)]
    case_context: CaseContext


class RecordEvaluation(JSONModel):
    suite_version_id: UUIDv4
    case_inputs: list[CaseInput] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_cases(self):
        if len({case.case_id for case in self.case_inputs}) != len(self.case_inputs):
            raise ValueError('duplicate case_id')
        return self


class SubmitChange(JSONModel):
    pass


def reason(value: str) -> str:
    if not 8 <= len(value) <= 500 or not 8 <= len(value.strip()) <= 500:
        raise ValueError('reason must contain 8 to 500 code points before and after strip')
    return value.strip()


class Decision(JSONModel):
    decision: Literal['APPROVE', 'REJECT']
    reason: Annotated[str, AfterValidator(reason)]


class CreateHeaders(JSONModel):
    key: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{12,128}\z', alias='Idempotency-Key')]

    @model_validator(mode='before')
    @classmethod
    def header_names(cls, value):
        if not isinstance(value, dict):
            return value
        names = {'idempotency-key': 'Idempotency-Key', 'x-expected-revision': 'X-Expected-Revision'}
        extracted = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError('invalid header name')
            target = names.get(key.lower(), key)
            if target in extracted:
                raise ValueError('duplicate protocol header')
            extracted[target] = item
        return extracted


class MutationHeaders(CreateHeaders):
    expected_revision: Annotated[str, Field(pattern=r'^[1-9][0-9]*\z', alias='X-Expected-Revision', max_length=16)]

    @model_validator(mode='after')
    def safe_revision(self):
        if int(self.expected_revision) > MAX_REVISION:
            raise ValueError('revision outside safe integer range')
        return self

    @property
    def revision(self) -> int:
        return int(self.expected_revision)


class ChangeRevision(CreateChange):
    schema_name: Literal['change_revision_v1'] = Field(alias='schema')
    tenant_id: RegisteredId
    change_id: UUIDv4
    revision: Revision
    status: Status
    requester_id: RegisteredId
    owner_id: RegisteredId
    domain_reviewer_id: RegisteredId | None
    release_approver_id: RegisteredId | None
    active_run_id: UUIDv4 | None
    active_job_id: None
    parent_change_id: UUIDv4 | None
    parent_relation: ParentRelation | None
    assessment_sha256: SHA256 | None
    created_at: UTCTimestamp
    updated_at: UTCTimestamp

    @model_validator(mode='after')
    def state_fields(self):
        if self.status in ('PENDING_DOMAIN_REVIEW', 'PENDING_RELEASE', 'APPROVED_FOR_DEMO') and self.active_run_id is None:
            raise ValueError('submitted change requires a selected run')
        if self.status in ('DRAFT', 'PENDING_DOMAIN_REVIEW') and (self.domain_reviewer_id or self.release_approver_id):
            raise ValueError('unexpected reviewer')
        if self.status == 'APPROVED_FOR_DEMO':
            if not self.domain_reviewer_id or not self.release_approver_id or not self.assessment_sha256:
                raise ValueError('approved snapshot requires actors and assessment')
        elif self.assessment_sha256 is not None:
            raise ValueError('assessment only belongs to approved snapshot')
        return self


class DecisionNote(JSONModel):
    schema_name: Literal['decision_note_v1'] = Field(alias='schema')
    tenant_id: RegisteredId
    id: UUIDv4
    change_id: UUIDv4
    stage: Literal['DOMAIN', 'RELEASE']
    decision: Literal['APPROVE', 'REJECT']
    actor_id: RegisteredId
    input_revision: Revision
    output_revision: Revision
    reason: str
    occurred_at: UTCTimestamp
    assessment_sha256: SHA256 | None

    @model_validator(mode='after')
    def bindings(self):
        if reason(self.reason) != self.reason or self.output_revision != self.input_revision + 1:
            raise ValueError('noncanonical note or invalid revision binding')
        needs_assessment = self.stage == 'RELEASE' and self.decision == 'APPROVE'
        if needs_assessment != (self.assessment_sha256 is not None):
            raise ValueError('invalid note assessment')
        return self


class PayloadRef(JSONModel):
    id: UUIDv4
    payload_sha256: SHA256


class CaseResult(JSONModel):
    case_id: RegisteredId
    input_sha256: SHA256
    output_sha256: SHA256
    source_refs: list[PayloadRef]
    resolution_status: RegisteredId
    verdict: Literal['PASS', 'FAIL', 'INCONCLUSIVE']
    complete: bool
    error_code: RegisteredId | None
    critical_failure: bool | None

    @model_validator(mode='after')
    def incomplete_and_sources(self):
        refs = [(ref.id, ref.payload_sha256) for ref in self.source_refs]
        if len(set(refs)) != len(refs):
            raise ValueError('duplicate source reference')
        if not self.complete and (self.verdict != 'INCONCLUSIVE' or self.critical_failure is not None or self.error_code is None):
            raise ValueError('incomplete result must record uncertainty and cause')
        return self


class EvaluationRun(JSONModel):
    schema_name: Literal['evaluation_run_v1'] = Field(alias='schema')
    id: UUIDv4
    tenant_id: RegisteredId
    change_id: UUIDv4
    recorded_revision: Revision
    actor_id: RegisteredId
    created_at: UTCTimestamp
    candidate_snapshot_id: UUIDv4
    source_bundle_id: UUIDv4
    dataset_version_id: UUIDv4
    suite_version_id: UUIDv4
    evaluator_version_id: UUIDv4
    adapter_version_id: UUIDv4
    run_input_sha256: SHA256
    run_config_sha256: SHA256
    case_results: list[CaseResult]
    completion: Literal['COMPLETE', 'INCOMPLETE']
    gate_summary: Literal['PASS', 'BLOCK']

    @model_validator(mode='after')
    def result_consistency(self):
        ids = [case.case_id for case in self.case_results]
        if ids != sorted(set(ids)):
            raise ValueError('case_results must be sorted and unique by case_id')
        if self.completion == 'COMPLETE' and (not ids or not all(case.complete for case in self.case_results)):
            raise ValueError('complete run contains incomplete results')
        if self.gate_summary == 'PASS' and (self.completion != 'COMPLETE' or not ids or
                any(case.verdict != 'PASS' or case.critical_failure is not False for case in self.case_results)):
            raise ValueError('PASS requires complete passing results')
        return self


class EvaluationRunV2(EvaluationRun):
    schema_name: Literal['evaluation_run_v2'] = Field(alias='schema')


Model = TypeVar('Model', bound=JSONModel)


def parse_body(model: type[Model], raw: bytes | str) -> Model:
    return model.model_validate(parse_json(raw))
