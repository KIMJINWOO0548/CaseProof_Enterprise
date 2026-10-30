"""Pure G1 workflow rules, with IDs/time and verified facts supplied by the executor.

Internal command: kind, change_id, occurred_at, expected_revision, body, checks;
optional run, note, domain_note and parent contain canonical stored payloads.
TransitionChecks must be a server-created instance, never a parsed HTTP object.
It binds externally computed history/gate/source/assessment checks to this exact
snapshot/run. It is an internal assertion, not cryptographic proof. G1.3 must
reconstruct history and G1.5 must compute the gate before constructing it.
This module neither authenticates actors nor writes side records or envelopes.
"""
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, InstanceOf, TypeAdapter, ValidationError

from service.api.errors import DomainError
from service.api.schemas_v1 import (
    MAX_REVISION, SHA256, UUIDv4, UTCTimestamp, ChangeRevision, CreateChange, Decision,
    DecisionNote, EvaluationRun, RecordEvaluation, RegisteredId, Revision, SubmitChange,
)
from service.domain.canonical import content_hash
from service.domain.types import ActorContext

TABLE = {
    'CHANGE_CREATED': ('NONE', 'DRAFT', 'ANALYST'),
    'EVALUATION_RECORDED': ('DRAFT', 'DRAFT', 'ANALYST'),
    'SUBMITTED_FOR_DOMAIN_REVIEW': ('DRAFT', 'PENDING_DOMAIN_REVIEW', 'ANALYST'),
    'DOMAIN_APPROVE': ('PENDING_DOMAIN_REVIEW', 'PENDING_RELEASE', 'DOMAIN_REVIEWER'),
    'DOMAIN_REJECT': ('PENDING_DOMAIN_REVIEW', 'REJECTED', 'DOMAIN_REVIEWER'),
    'APPROVED_FOR_DEMO': ('PENDING_RELEASE', 'APPROVED_FOR_DEMO', 'RELEASE_APPROVER'),
    'RELEASE_REJECT': ('PENDING_RELEASE', 'REJECTED', 'RELEASE_APPROVER'),
}
SNAPSHOT_IDS = ('candidate_snapshot_id', 'source_bundle_id', 'dataset_version_id', 'suite_version_id', 'evaluator_version_id')


@dataclass(frozen=True)
class TransitionChecks:
    tenant_id: str
    change_id: str
    revision: int
    snapshot_sha256: str | None
    gate_run_sha256: str | None = None
    source_bundle_id: str | None = None
    source_eligible: bool = False
    assessment_sha256: str | None = None

    def __post_init__(self):
        TypeAdapter(tuple[RegisteredId, UUIDv4, Annotated[int, Field(ge=0, le=MAX_REVISION)],
                          SHA256 | None, SHA256 | None, UUIDv4 | None, bool, SHA256 | None]).validate_python(
            (self.tenant_id, self.change_id, self.revision, self.snapshot_sha256,
             self.gate_run_sha256, self.source_bundle_id, self.source_eligible, self.assessment_sha256), strict=True)


class _Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    kind: Literal['CHANGE_CREATED', 'EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW',
                  'DOMAIN_APPROVE', 'DOMAIN_REJECT', 'APPROVED_FOR_DEMO', 'RELEASE_REJECT']
    change_id: UUIDv4
    occurred_at: UTCTimestamp
    expected_revision: Revision | None
    body: dict
    checks: InstanceOf[TransitionChecks]
    run: dict | None = None
    note: dict | None = None
    domain_note: dict | None = None
    parent: dict | None = None


def _parse(model, value, code='EVIDENCE_RECORD_TAMPERED'):
    try:
        return model.model_validate(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise DomainError(code) from exc


def _require(condition, code='EVIDENCE_RECORD_TAMPERED'):
    if not condition:
        raise DomainError(code)


def _run(command, snapshot):
    run = _parse(EvaluationRun, command.run)
    _require(run.tenant_id == snapshot['tenant_id'] and run.change_id == snapshot['change_id'])
    _require(all(getattr(run, key) == snapshot[key] for key in SNAPSHOT_IDS), 'SNAPSHOT_MISMATCH')
    _require(run.actor_id == snapshot['requester_id'])
    return run


def _gate(command, run):
    _require(run.completion == 'COMPLETE', 'EVALUATION_INCOMPLETE')
    _require(run.gate_summary == 'PASS' and command.checks.gate_run_sha256 ==
             content_hash('evaluation-run', run.model_dump(by_alias=True)), 'RELEASE_GATE_BLOCKED')


def _note(command, snapshot, actor, stage, decision):
    note = _parse(DecisionNote, command.note)
    _require(note.tenant_id == actor.tenant_id and note.change_id == snapshot['change_id'] and
             note.actor_id == actor.actor_id and note.stage == stage and note.decision == decision and
             note.input_revision == snapshot['revision'] and note.output_revision == snapshot['revision'] + 1 and
             note.occurred_at == command.occurred_at)
    body = _parse(Decision, command.body, 'INVALID_REQUEST')
    _require(body.decision == note.decision and body.reason == note.reason)
    return note


def apply_transition(snapshot: dict | None, command: dict, actor: ActorContext) -> dict:
    """Return a new canonical snapshot or fail without mutating either input."""
    command = _parse(_Command, command, 'INVALID_REQUEST')
    _require(isinstance(actor, ActorContext), 'FORBIDDEN')
    try:
        TypeAdapter(tuple[RegisteredId, RegisteredId]).validate_python((actor.tenant_id, actor.actor_id), strict=True)
    except ValidationError as exc:
        raise DomainError('FORBIDDEN') from exc
    old = _parse(ChangeRevision, snapshot).model_dump(by_alias=True) if snapshot is not None else None
    checks = command.checks
    _require(checks.tenant_id == actor.tenant_id and (old is None or old['tenant_id'] == actor.tenant_id), 'NOT_FOUND')
    _require(command.change_id == checks.change_id and (old is None or command.change_id == old['change_id']), 'NOT_FOUND')
    _require(checks.revision == (old['revision'] if old else 0) and checks.snapshot_sha256 ==
             (content_hash('change-revision', old) if old else None))
    from_state, to_state, role = TABLE[command.kind]
    _require(from_state == (old['status'] if old else 'NONE'), 'INVALID_STATUS')
    _require(role in actor.roles, 'FORBIDDEN')
    if old is None:
        _require(command.expected_revision is None, 'INVALID_REQUEST')
        body = _parse(CreateChange, command.body, 'INVALID_REQUEST').model_dump()
        _require(command.run is None and command.note is None and command.domain_note is None, 'INVALID_REQUEST')
        if body['parent_change_id'] is not None:
            parent = _parse(ChangeRevision, command.parent)
            _require(parent.tenant_id == actor.tenant_id and parent.change_id == body['parent_change_id'], 'NOT_FOUND')
            _require(parent.change_id != command.change_id, 'INVALID_REQUEST')
            expected = {'CORRECTS_REJECTED': 'REJECTED', 'REPLACES_DRAFT': 'DRAFT', 'FOLLOWS_APPROVED': 'APPROVED_FOR_DEMO'}
            _require(parent.status == expected[body['parent_relation']], 'INVALID_STATUS')
        else:
            _require(command.parent is None, 'INVALID_REQUEST')
        result = dict(body, schema='change_revision_v1', tenant_id=actor.tenant_id, change_id=command.change_id,
                      revision=1, status='DRAFT', requester_id=actor.actor_id, owner_id=actor.actor_id,
                      domain_reviewer_id=None, release_approver_id=None, active_run_id=None, active_job_id=None,
                      assessment_sha256=None, created_at=command.occurred_at, updated_at=command.occurred_at)
        return _parse(ChangeRevision, result).model_dump(by_alias=True)

    _require(command.expected_revision is not None, 'INVALID_REQUEST')
    if command.expected_revision != old['revision']:
        raise DomainError('STALE_REVISION', current_revision=old['revision'])
    _require(old['revision'] < MAX_REVISION and command.occurred_at >= old['updated_at'], 'INVALID_REQUEST')
    _require(command.parent is None, 'INVALID_REQUEST')
    if role == 'ANALYST':
        _require(actor.actor_id == old['requester_id'], 'REQUESTER_ONLY')
    else:
        _require(actor.actor_id not in (old['requester_id'], old['owner_id']), 'SEPARATION_OF_DUTIES')
        if role == 'RELEASE_APPROVER':
            _require(actor.actor_id != old['domain_reviewer_id'], 'SEPARATION_OF_DUTIES')

    result = dict(old, revision=old['revision'] + 1, status=to_state, updated_at=command.occurred_at)
    if command.kind in ('EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW'):
        _require(command.note is None and command.domain_note is None, 'INVALID_REQUEST')
        run = _run(command, old)
        if command.kind == 'EVALUATION_RECORDED':
            body = _parse(RecordEvaluation, command.body, 'INVALID_REQUEST')
            _require(body.suite_version_id == old['suite_version_id'], 'SNAPSHOT_MISMATCH')
            _require(run.recorded_revision == result['revision'] and run.created_at == command.occurred_at)
            _require(run.id != old['active_run_id'])
            result['active_run_id'] = run.id
        else:
            _parse(SubmitChange, command.body, 'INVALID_REQUEST')
            _require(run.id == old['active_run_id'] and run.recorded_revision == old['revision'])
            _gate(command, run)
    else:
        stage = 'DOMAIN' if role == 'DOMAIN_REVIEWER' else 'RELEASE'
        decision = 'REJECT' if command.kind.endswith('REJECT') else 'APPROVE'
        note = _note(command, old, actor, stage, decision)
        if stage == 'DOMAIN':
            _require(command.run is None and command.domain_note is None, 'INVALID_REQUEST')
            result['domain_reviewer_id'] = actor.actor_id
        else:
            domain = _parse(DecisionNote, command.domain_note)
            _require(domain.tenant_id == actor.tenant_id and domain.change_id == old['change_id'] and
                     domain.stage == 'DOMAIN' and domain.decision == 'APPROVE' and
                     domain.actor_id == old['domain_reviewer_id'] and domain.output_revision == old['revision'] and
                     domain.actor_id not in (old['requester_id'], old['owner_id']) and domain.occurred_at <= command.occurred_at and
                     note.id != domain.id)
            result['release_approver_id'] = actor.actor_id
            if decision == 'APPROVE':
                run = _run(command, old)
                _require(run.id == old['active_run_id'] and run.recorded_revision == domain.input_revision - 1)
                _gate(command, run)
                _require(checks.source_eligible and checks.source_bundle_id == old['source_bundle_id'], 'SOURCE_NOT_ELIGIBLE')
                _require(checks.assessment_sha256 is not None and checks.assessment_sha256 == note.assessment_sha256)
                result['assessment_sha256'] = checks.assessment_sha256
            else:
                _require(command.run is None, 'INVALID_REQUEST')
    return _parse(ChangeRevision, result).model_dump(by_alias=True)
