"""One authoritative transaction for all seven v1 workflow commands."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from service import models_v1 as m
from service.api.errors import DomainError
from service.api.schemas_v1 import CreateChange, Decision, RecordEvaluation, SubmitChange, CreateHeaders, MutationHeaders
from service.auth import current_actor
from service.domain.canonical import content_hash
from service.domain.state_machine import TABLE, TransitionChecks, apply_transition
from service.domain.types import CommandContext, CommandResult, json_payload
from service.idempotency_v1 import fingerprint, lookup, replay
from service.repositories import ZERO, add_payload, get_change, load_history, load_refs, lock_related, require

BASE = '/api/v1/changes'
ROUTES = {BASE: ('CHANGE_CREATED', CreateChange), BASE + '/{change_id}/evaluation-runs': ('EVALUATION_RECORDED', RecordEvaluation),
    BASE + '/{change_id}/submit': ('SUBMITTED_FOR_DOMAIN_REVIEW', SubmitChange),
    BASE + '/{change_id}/domain-decision': ('DOMAIN', Decision), BASE + '/{change_id}/release-decision': ('RELEASE', Decision)}


def checkpoint(stage):
    """Exception-injection seam; no effects in normal operation."""


def normalize(command):
    try:
        require(command.method == 'POST' and command.route_template in ROUTES, 'INVALID_REQUEST')
        kind, model = ROUTES[command.route_template]
        body = model.model_validate(json_payload(command.body)).model_dump()
        if kind == 'CHANGE_CREATED':
            require(command.resource_id == 'NEW' and command.expected_revision is None, 'INVALID_REQUEST')
            CreateHeaders.model_validate({'Idempotency-Key': command.key})
        else:
            MutationHeaders.model_validate({'Idempotency-Key': command.key, 'X-Expected-Revision': str(command.expected_revision)})
        if kind in ('DOMAIN', 'RELEASE'):
            kind = ('APPROVED_FOR_DEMO' if kind == 'RELEASE' and body['decision'] == 'APPROVE' else kind + '_' + body['decision'])
        return kind, CommandContext(command.method, command.route_template, command.resource_id, command.key, command.expected_revision, body)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, DomainError):
            raise
        raise DomainError('INVALID_REQUEST') from None


def authorize(actor, kind, change=None):
    role = TABLE[kind][2]
    require(role in actor.roles, 'FORBIDDEN')
    if change is not None:
        if role == 'ANALYST':
            require(actor.actor_id == change.requester_id, 'REQUESTER_ONLY')
        else:
            require(actor.actor_id not in (change.requester_id, change.owner_id), 'SEPARATION_OF_DUTIES')
            if role == 'RELEASE_APPROVER':
                require(actor.actor_id != change.domain_reviewer_id, 'SEPARATION_OF_DUTIES')


def execute_command(session_factory, actor, command):
    kind, command = normalize(command)
    try:
        with session_factory() as db:
            with db.begin():
                actor = current_actor(db, actor)
                head = db.execute(select(m.TenantAuditHead).where(m.TenantAuditHead.tenant_id == actor.tenant_id).with_for_update()).scalar_one_or_none()
                change = None if kind == 'CHANGE_CREATED' else get_change(db, actor.tenant_id, command.resource_id, lock=True)
                authorize(actor, kind, change)
                lock_related(db, actor.tenant_id)
                existing = lookup(db, actor, command.key)
                if existing:
                    return replay(existing, command)
                require(head is not None, 'AUDIT_INTEGRITY_FAILURE')
                return _execute(db, actor, command, kind, change, head)
    except DBAPIError as exc:
        code = getattr(exc.orig, 'sqlstate', None)
        if code in ('40P01', '55P03', '40001') or 'database is locked' in str(exc.orig).lower():
            raise DomainError('RETRYABLE_CONFLICT') from None
        if exc.connection_invalidated:
            raise DomainError('OUTCOME_UNKNOWN') from None
        if isinstance(exc, IntegrityError):
            raise DomainError('EVIDENCE_RECORD_TAMPERED') from None
        raise


def _execute(db, actor, command, kind, change, head):
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    identity = str(uuid4()) if change is None else change.id
    body = json_payload(command.body)
    history = load_history(db, actor.tenant_id, identity) if change else None
    old = history['snapshot'] if history else None
    revision = old['revision'] if old else 0
    require(TABLE[kind][0] == (old['status'] if old else 'NONE'), 'INVALID_STATUS')
    if old and command.expected_revision != revision:
        raise DomainError('STALE_REVISION', current_revision=revision)
    parent = None
    if not old:
        # Validate the existing tenant chain even when creating another change.
        from service.repositories import rows, decode
        events = sorted([decode(row) for row in rows(db, m.AuditEvent, actor.tenant_id)], key=lambda p: p['sequence'])
        previous = ZERO
        for index, event in enumerate(events, 1):
            require(event['sequence'] == index and event['prev_hash'] == previous, 'AUDIT_INTEGRITY_FAILURE')
            previous = content_hash('audit-event', event)
        require(head.sequence == len(events) and head.head_sha256 == previous, 'AUDIT_INTEGRITY_FAILURE')
        load_refs(db, actor.tenant_id, body)
        if body.get('parent_change_id'):
            parent = load_history(db, actor.tenant_id, body['parent_change_id'])['snapshot']
    run = note = assessment = domain_note = None
    gate_hash = assessment_hash = None
    source_eligible = False
    if kind == 'EVALUATION_RECORDED':
        from service.evaluation.runner import prepare_run
        run = prepare_run(history, body, actor, str(uuid4()), now, revision + 1)
    if kind in ('SUBMITTED_FOR_DOMAIN_REVIEW', 'APPROVED_FOR_DEMO'):
        from service.domain.gates import check_run_gate, source_eligibility
        require(bool(history['runs']), 'EVALUATION_INCOMPLETE')
        run = history['runs'][-1]
        require(run['id'] == old['active_run_id'], 'EVIDENCE_RECORD_TAMPERED')
        gate = check_run_gate(run, history['refs']['suite'], source_eligibility(history))
        require(gate['completion'] == 'COMPLETE', 'EVALUATION_INCOMPLETE')
        require(gate['gate_summary'] == 'PASS', 'RELEASE_GATE_BLOCKED')
        gate_hash = content_hash('evaluation-run', run)
        source_eligible = gate['source_eligible']
    if kind in ('APPROVED_FOR_DEMO', 'RELEASE_REJECT'):
        domain_note = next((note for note in history['decisions'] if note['stage'] == 'DOMAIN'), None)
    if kind == 'APPROVED_FOR_DEMO':
        from service.domain.evidence import build_assessment
        require(source_eligible, 'SOURCE_NOT_ELIGIBLE')
        assessment = build_assessment(history, revision)
        assessment_hash = content_hash('assessment', assessment)
    if kind.startswith('DOMAIN_') or kind in ('APPROVED_FOR_DEMO', 'RELEASE_REJECT'):
        note = {'schema': 'decision_note_v1', 'tenant_id': actor.tenant_id, 'id': str(uuid4()), 'change_id': identity,
            'stage': 'DOMAIN' if kind.startswith('DOMAIN_') else 'RELEASE', 'decision': body['decision'],
            'actor_id': actor.actor_id, 'input_revision': revision, 'output_revision': revision + 1,
            'reason': body['reason'], 'occurred_at': now, 'assessment_sha256': assessment_hash}
    checks = TransitionChecks(actor.tenant_id, identity, revision, content_hash('change-revision', old) if old else None,
        gate_hash, old['source_bundle_id'] if old else None, source_eligible, assessment_hash)
    snapshot = apply_transition(old, {'kind': kind, 'change_id': identity, 'occurred_at': now,
        'expected_revision': command.expected_revision, 'body': body, 'checks': checks,
        'run': run, 'note': note, 'domain_note': domain_note, 'parent': parent}, actor)
    snapshot_hash = content_hash('change-revision', snapshot)
    transition_run = run if kind in ('EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW') else None
    transition = {'schema': 'change_transition_v1', 'tenant_id': actor.tenant_id, 'id': str(uuid4()), 'change_id': identity,
        'revision_from': revision, 'revision_to': revision + 1, 'from_state': old['status'] if old else 'NONE',
        'to_state': snapshot['status'], 'kind': kind, 'actor_id': actor.actor_id, 'occurred_at': now,
        'previous_snapshot_sha256': checks.snapshot_sha256, 'next_snapshot_sha256': snapshot_hash,
        'evaluation_run_id': transition_run['id'] if transition_run else None,
        'evaluation_run_sha256': content_hash('evaluation-run', transition_run) if transition_run else None,
        'decision_id': note['id'] if note else None, 'decision_sha256': content_hash('decision', note) if note else None,
        'assessment_sha256': assessment_hash}
    event = {'schema': 'audit_event_v1', 'tenant_id': actor.tenant_id, 'id': str(uuid4()), 'sequence': head.sequence + 1,
        'prev_hash': head.head_sha256, 'actor_id': actor.actor_id, 'occurred_at': now, 'subject_type': 'CHANGE',
        'subject_id': identity, 'kind': kind, 'transition_id': transition['id'], 'transition_sha256': content_hash('transition', transition)}
    values = {column.name: snapshot[column.name] for column in m.Change.__table__.columns if column.name in snapshot}
    if change is None:
        change = m.Change(id=identity, approval_envelope_sha256=None, **dict(values, revision=0, status='INCOMPLETE'))
        db.add(change)
        db.flush()
    else:
        changed = db.execute(update(m.Change).where(m.Change.tenant_id == actor.tenant_id, m.Change.id == identity,
            m.Change.revision == revision).values(**values)).rowcount
        require(changed == 1, 'RETRYABLE_CONFLICT')
    checkpoint('projection')
    if assessment:
        _save_assessment(db, assessment)
    if note:
        add_payload(db, m.DecisionNote, note)
    checkpoint('note')
    if kind == 'EVALUATION_RECORDED':
        add_payload(db, m.EvaluationRun, run)
        for case in run['case_results']:
            for ref in case['source_refs']:
                db.add(m.RunSourceRef(tenant_id=actor.tenant_id, id=str(uuid4()), run_id=run['id'], case_id=case['case_id'], source_id=ref['id']))
        db.flush()
    add_payload(db, m.ChangeRevision, snapshot)
    checkpoint('snapshot')
    add_payload(db, m.ChangeTransition, transition)
    checkpoint('transition')
    add_payload(db, m.AuditEvent, event)
    checkpoint('audit')
    head.sequence, head.head_sha256 = event['sequence'], content_hash('audit-event', event)
    db.flush()
    checkpoint('head')
    envelope_hash = None
    if assessment:
        from service.domain.evidence import build_envelope
        envelope = build_envelope(assessment, snapshot, note, transition, event)
        add_payload(db, m.ApprovalEnvelope, envelope, id=str(uuid4()), release_decision_id=note['id'],
                    release_transition_id=transition['id'], release_event_id=event['id'])
        envelope_hash = content_hash('approval-envelope', envelope)
    db.execute(update(m.Change).where(m.Change.tenant_id == actor.tenant_id, m.Change.id == identity).values(
        **values, approval_envelope_sha256=envelope_hash))
    status = 201 if kind in ('CHANGE_CREATED', 'EVALUATION_RECORDED') else 200
    data = dict(snapshot)
    if kind == 'EVALUATION_RECORDED':
        data['run'] = run
    result = CommandResult(status, data, revision + 1, False)
    record = {'schema': 'idempotency_record_v1', 'tenant_id': actor.tenant_id, 'actor_id': actor.actor_id, 'key': command.key,
        'request_sha256': fingerprint(command), 'method': command.method, 'route_template': command.route_template,
        'resource_id': command.resource_id, 'response_status': status, 'response_data_json': data, 'result_revision': revision + 1,
        'created_at': now, 'completed_at': now, 'completion': 'COMMITTED'}
    add_payload(db, m.IdempotencyRecord, record, id=str(uuid4()), change_id=identity, original_status=status,
                fingerprint_sha256=fingerprint(command))
    checkpoint('idempotency')
    return result


def _save_assessment(db, assessment):
    identity = str(uuid4())
    refs = {'candidate_snapshot_id': 'candidate_snapshot_ref', 'source_bundle_id': 'source_bundle_ref',
            'dataset_version_id': 'dataset_ref', 'suite_version_id': 'suite_ref', 'evaluator_version_id': 'evaluator_ref',
            'model_id': 'model_ref', 'prompt_id': 'prompt_ref', 'source_eligibility_snapshot_id': 'source_eligibility_snapshot_ref'}
    add_payload(db, m.Assessment, assessment, id=identity,
                **{key: assessment[name]['id'] if assessment[name] else None for key, name in refs.items()})
    for name, model, field in (('run_refs', m.AssessmentRunRef, 'run_id'), ('decision_refs', m.AssessmentDecisionRef, 'decision_id'),
                               ('transition_refs', m.AssessmentTransitionRef, 'transition_id')):
        for ref in assessment[name]:
            values = {field: ref['id']}
            if name == 'transition_refs':
                values['event_id'] = ref['audit_event_ref']['id']
            db.add(model(tenant_id=assessment['tenant_id'], id=str(uuid4()), assessment_id=identity, **values))
    db.flush()
