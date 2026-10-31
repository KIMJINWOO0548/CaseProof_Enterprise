"""Tenant-scoped records and deterministic immutable-history reconstruction."""
from sqlalchemy import select
from service import models_v1 as m
from service.api.errors import DomainError
from service.api.schemas_v1 import ChangeRevision, DecisionNote, EvaluationRun, EvaluationRunV2
from service.domain.canonical import canonical_bytes, content_hash, parse_json
from service.domain.state_machine import TABLE, SNAPSHOT_IDS
from service.evaluation.config import execution_config_sha256

ZERO = '0' * 64
PURPOSES = {m.ChangeRevision: 'change-revision', m.ChangeTransition: 'transition', m.AuditEvent: 'audit-event',
    m.EvaluationRun: 'evaluation-run', m.DecisionNote: 'decision', m.Assessment: 'assessment',
    m.ApprovalEnvelope: 'approval-envelope', m.CandidateSnapshot: 'candidate', m.SourceBundle: 'source-bundle',
    m.SourceSnapshot: 'source', m.PolicySnapshot: 'policy', m.ModelSnapshot: 'model', m.PromptSnapshot: 'prompt',
    m.DatasetSnapshot: 'dataset', m.SuiteSnapshot: 'suite', m.EvaluatorSnapshot: 'evaluator',
    m.AdapterSnapshot: 'adapter', m.SourceEligibilitySnapshot: 'source-eligibility', m.IdempotencyRecord: 'idempotency'}


def require(condition, code='EVIDENCE_RECORD_TAMPERED'):
    if not condition:
        raise DomainError(code)


def decode(row, purpose=None):
    try:
        data = parse_json(row.canonical_payload)
        require(isinstance(data, dict))
        require(canonical_bytes(data) == row.canonical_payload)
        require(content_hash(purpose or PURPOSES[type(row)], data) == row.payload_sha256)
        require(data.get('schema') == row.schema_version)
        require(data.get('tenant_id') == row.tenant_id)
        if 'id' in row.__table__.columns and not isinstance(row, (m.Assessment, m.ApprovalEnvelope, m.IdempotencyRecord)):
            require(data.get('id') == row.id)
        for column in row.__table__.columns:
            if column.name in data:
                require(getattr(row, column.name) == data[column.name])
        nested_refs = {
            m.Assessment: {'candidate_snapshot_id': 'candidate_snapshot_ref', 'source_bundle_id': 'source_bundle_ref',
                'dataset_version_id': 'dataset_ref', 'suite_version_id': 'suite_ref', 'evaluator_version_id': 'evaluator_ref',
                'model_id': 'model_ref', 'prompt_id': 'prompt_ref', 'source_eligibility_snapshot_id': 'source_eligibility_snapshot_ref'},
            m.ApprovalEnvelope: {'release_decision_id': 'release_decision_ref', 'release_transition_id': 'release_transition_ref',
                'release_event_id': 'release_event_ref'},
        }
        for column, name in nested_refs.get(type(row), {}).items():
            ref = data[name]
            require(isinstance(ref, dict) or (ref is None and column in ('model_id', 'prompt_id')))
            require(getattr(row, column) == (ref['id'] if ref is not None else None))
        if isinstance(row, m.IdempotencyRecord):
            require(row.change_id == data['response_data_json']['change_id'])
        run_model = EvaluationRunV2 if data.get('schema') == 'evaluation_run_v2' else EvaluationRun
        model = {m.ChangeRevision: ChangeRevision, m.DecisionNote: DecisionNote, m.EvaluationRun: run_model}.get(type(row))
        if model:
            require(model.model_validate(data).model_dump(by_alias=True) == data)
        return data
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, DomainError):
            raise
        raise DomainError('EVIDENCE_RECORD_TAMPERED') from None


def add_payload(db, model, data, **extra):
    values = {column.name: data[column.name] for column in model.__table__.columns if column.name in data}
    values.update(schema_version=data['schema'], canonical_payload=canonical_bytes(data),
                  payload_sha256=content_hash(PURPOSES[model], data), **extra)
    row = model(**values)
    db.add(row)
    db.flush()
    return row


def get_change(db, tenant_id, change_id, lock=False):
    statement = select(m.Change).where(m.Change.tenant_id == tenant_id, m.Change.id == change_id)
    row = db.execute(statement.with_for_update() if lock else statement).scalar_one_or_none()
    if row is None:
        raise DomainError('NOT_FOUND')
    return row


def rows(db, model, tenant_id, **filters):
    query = select(model).where(model.tenant_id == tenant_id)
    for name, value in filters.items():
        query = query.where(getattr(model, name) == value)
    return list(db.execute(query.order_by(*model.__table__.primary_key.columns)).scalars())


def load_refs(db, tenant_id, snapshot):
    def one(model, identity):
        row = db.get(model, (tenant_id, identity))
        require(row is not None, 'SNAPSHOT_MISMATCH')
        return decode(row)
    refs = {name: one(model, snapshot[key]) for name, model, key in (
        ('candidate_snapshot', m.CandidateSnapshot, 'candidate_snapshot_id'),
        ('source_bundle', m.SourceBundle, 'source_bundle_id'), ('dataset', m.DatasetSnapshot, 'dataset_version_id'),
        ('suite', m.SuiteSnapshot, 'suite_version_id'), ('evaluator', m.EvaluatorSnapshot, 'evaluator_version_id'))}
    candidate = refs['candidate_snapshot']
    refs['model'] = one(m.ModelSnapshot, candidate['model_id']) if candidate.get('model_id') else None
    refs['prompt'] = one(m.PromptSnapshot, candidate['prompt_id']) if candidate.get('prompt_id') else None
    members = rows(db, m.SourceBundleMember, tenant_id, source_bundle_id=snapshot['source_bundle_id'])
    refs['sources'] = [one(m.SourceSnapshot, identity) for identity in sorted({row.source_id for row in members})]
    refs['policies'] = [one(m.PolicySnapshot, identity) for identity in sorted({row.policy_id for row in members})]
    adapter_id = candidate.get('adapter_version_id')
    refs['adapters'] = [one(m.AdapterSnapshot, adapter_id)] if adapter_id else []
    refs['source_eligibility'] = [decode(row) for row in rows(db, m.SourceEligibilitySnapshot, tenant_id,
                                                           source_bundle_id=snapshot['source_bundle_id'])]
    # Bundle member rows must be authenticated by the immutable bundle itself.
    sealed_members = refs['source_bundle'].get('members', [])
    require(bool(sealed_members))
    require(sorted((r.source_id, r.policy_id) for r in members) ==
            sorted((r['source_id'], r['policy_id']) for r in sealed_members))
    for member in sealed_members:
        require(content_hash('source', one(m.SourceSnapshot, member['source_id'])) == member['source_sha256'])
        require(content_hash('policy', one(m.PolicySnapshot, member['policy_id'])) == member['policy_sha256'])
    return refs


def lock_related(db, tenant_id):
    # Tenant head serializes writers; immutable rows need no UPDATE privilege for row locks.
    excluded = {m.Change.__table__.name, m.TenantAuditHead.__table__.name, m.IdempotencyRecord.__table__.name,
                m.Actor.__table__.name, m.Tenant.__table__.name}
    for table in sorted(m.BaseV1.metadata.tables.values(), key=lambda table: table.name):
        if table.name not in excluded:
            db.execute(select(table).where(table.c.tenant_id == tenant_id).order_by(*table.primary_key.columns)).all()


def load_history(db, tenant_id, change_id):
    try:
        return _load_history(db, tenant_id, change_id)
    except (KeyError, IndexError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, DomainError):
            raise
        raise DomainError('EVIDENCE_RECORD_TAMPERED') from None


def _load_history(db, tenant_id, change_id):
    projection = get_change(db, tenant_id, change_id)
    history = {}
    for name, model in (('snapshots', m.ChangeRevision), ('transitions', m.ChangeTransition),
                        ('runs', m.EvaluationRun), ('decisions', m.DecisionNote)):
        history[name] = [decode(row) for row in rows(db, model, tenant_id, change_id=change_id)]
    require(all(run['schema'] == 'evaluation_run_v2' for run in history['runs']), 'EXECUTION_CONFIG_UNVERIFIED')
    snapshots = sorted(history['snapshots'], key=lambda p: p['revision'])
    transitions = sorted(history['transitions'], key=lambda p: p['revision_to'])
    history['snapshots'], history['transitions'] = snapshots, transitions
    history['runs'].sort(key=lambda p: (p['recorded_revision'], p['id']))
    history['decisions'].sort(key=lambda p: (p['output_revision'], p['id']))
    tenant_events = sorted([decode(row) for row in rows(db, m.AuditEvent, tenant_id)], key=lambda p: p['sequence'])
    head = db.get(m.TenantAuditHead, tenant_id)
    require(head is not None, 'AUDIT_INTEGRITY_FAILURE')
    previous = ZERO
    for index, event in enumerate(tenant_events, 1):
        require(event['sequence'] == index and event['prev_hash'] == previous, 'AUDIT_INTEGRITY_FAILURE')
        require(event['subject_type'] == 'CHANGE', 'AUDIT_INTEGRITY_FAILURE')
        previous = content_hash('audit-event', event)
    require(head.sequence == len(tenant_events) and head.head_sha256 == previous, 'AUDIT_INTEGRITY_FAILURE')
    events = [event for event in tenant_events if event['subject_id'] == change_id]
    require(len(snapshots) == len(transitions) == len(events) == projection.revision and bool(snapshots))
    run_map = {p['id']: p for p in history['runs']}
    note_map = {p['id']: p for p in history['decisions']}
    seen_runs, seen_notes = set(), set()
    prior = None
    for index, (snapshot, transition, event) in enumerate(zip(snapshots, transitions, events), 1):
        kind = transition['kind']
        require(kind in TABLE)
        from_state, to_state, role = TABLE[kind]
        require(snapshot['revision'] == index and transition['revision_from'] == index - 1 and transition['revision_to'] == index)
        require(transition['from_state'] == from_state == (prior['status'] if prior else 'NONE'))
        require(snapshot['status'] == transition['to_state'] == to_state)
        require(transition['previous_snapshot_sha256'] == (content_hash('change-revision', prior) if prior else None))
        require(transition['next_snapshot_sha256'] == content_hash('change-revision', snapshot))
        require(event['transition_id'] == transition['id'] and event['transition_sha256'] == content_hash('transition', transition))
        require(event['actor_id'] == transition['actor_id'] and event['kind'] == kind and event['occurred_at'] == transition['occurred_at'] == snapshot['updated_at'])
        require(event['tenant_id'] == transition['tenant_id'] == snapshot['tenant_id'] == tenant_id)
        require(transition['change_id'] == snapshot['change_id'] == change_id)
        actor_id = transition['actor_id']
        if prior is None:
            require(snapshot['requester_id'] == snapshot['owner_id'] == actor_id)
            require(snapshot['created_at'] == snapshot['updated_at'] and snapshot['active_run_id'] is None)
            expected = dict(snapshot)
        else:
            require(snapshot['updated_at'] >= prior['updated_at'])
            expected = dict(prior, revision=index, status=to_state, updated_at=transition['occurred_at'])
            if role == 'ANALYST':
                require(actor_id == prior['requester_id'])
            else:
                require(actor_id not in (prior['requester_id'], prior['owner_id']))
                if role == 'RELEASE_APPROVER':
                    require(actor_id != prior['domain_reviewer_id'])
        if kind in ('EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW'):
            run = run_map[transition['evaluation_run_id']]
            require(transition['evaluation_run_sha256'] == content_hash('evaluation-run', run))
            require(all(run[key] == snapshot[key] for key in SNAPSHOT_IDS))
            require(run['actor_id'] == snapshot['requester_id'])
            if kind == 'EVALUATION_RECORDED':
                require(run['recorded_revision'] == index and run['created_at'] == transition['occurred_at'])
                expected['active_run_id'] = run['id']
                seen_runs.add(run['id'])
            else:
                require(run['id'] == prior['active_run_id'] and run['recorded_revision'] == index - 1)
                require(run['completion'] == 'COMPLETE' and run['gate_summary'] == 'PASS')
        else:
            require(transition['evaluation_run_id'] is None and transition['evaluation_run_sha256'] is None)
        if kind.startswith('DOMAIN_') or kind in ('RELEASE_REJECT', 'APPROVED_FOR_DEMO'):
            note = note_map[transition['decision_id']]
            require(transition['decision_sha256'] == content_hash('decision', note))
            stage = 'DOMAIN' if kind.startswith('DOMAIN_') else 'RELEASE'
            require(note['stage'] == stage and note['decision'] == ('REJECT' if kind.endswith('REJECT') else 'APPROVE'))
            require(note['actor_id'] == actor_id and note['input_revision'] == index - 1 and note['output_revision'] == index and note['occurred_at'] == transition['occurred_at'])
            expected['domain_reviewer_id' if stage == 'DOMAIN' else 'release_approver_id'] = actor_id
            seen_notes.add(note['id'])
            if kind == 'APPROVED_FOR_DEMO':
                require(note['assessment_sha256'] == transition['assessment_sha256'] == snapshot['assessment_sha256'])
                expected['assessment_sha256'] = note['assessment_sha256']
        else:
            require(transition['decision_id'] is None and transition['decision_sha256'] is None)
        if kind != 'APPROVED_FOR_DEMO':
            require(transition['assessment_sha256'] is None)
        require(expected == snapshot)
        prior = snapshot
    require(seen_runs == set(run_map) and seen_notes == set(note_map))
    for column in m.Change.__table__.columns:
        if column.name in prior:
            require(getattr(projection, column.name) == prior[column.name])
    history.update(snapshot=prior, events=events, tenant_events=tenant_events,
                   tenant_head={'sequence': head.sequence, 'head_sha256': head.head_sha256},
                   refs=load_refs(db, tenant_id, prior))
    for name, model in (('assessment', m.Assessment), ('envelope', m.ApprovalEnvelope)):
        found = rows(db, model, tenant_id, change_id=change_id)
        require(len(found) <= 1)
        history[name] = decode(found[0]) if found else None
        if name == 'assessment' and found:
            for key, link_model, fields in (
                ('run_refs', m.AssessmentRunRef, ('run_id',)),
                ('decision_refs', m.AssessmentDecisionRef, ('decision_id',)),
                ('transition_refs', m.AssessmentTransitionRef, ('transition_id', 'event_id')),
            ):
                refs = history[name][key]
                expected_links = [(ref['id'], ref['audit_event_ref']['id']) if len(fields) == 2 else (ref['id'],) for ref in refs]
                actual_rows = rows(db, link_model, tenant_id, assessment_id=found[0].id)
                actual_links = [tuple(getattr(row, field) for field in fields) for row in actual_rows]
                require(len(expected_links) == len(set(expected_links)) == len(actual_links))
                require(set(expected_links) == set(actual_links))
    require((history['assessment'] is not None) == (prior['status'] == 'APPROVED_FOR_DEMO'))
    require((history['envelope'] is not None) == (prior['status'] == 'APPROVED_FOR_DEMO'))
    require(projection.approval_envelope_sha256 == (content_hash('approval-envelope', history['envelope']) if history['envelope'] else None))
    for run in history['runs']:
        adapter = db.get(m.AdapterSnapshot, (tenant_id, run['adapter_version_id']))
        require(adapter is not None)
        adapter = decode(adapter)
        refs = history['refs']
        require(run['adapter_version_id'] == refs['candidate_snapshot'].get('adapter_version_id'))
        # A rehashed snapshot must still match the configuration bound by the run.
        require(run['run_config_sha256'] == execution_config_sha256(refs, adapter))
        expected_sources = {(case['case_id'], ref['id']) for case in run['case_results'] for ref in case['source_refs']}
        actual_sources = {(row.case_id, row.source_id) for row in rows(db, m.RunSourceRef, tenant_id, run_id=run['id'])}
        require(expected_sources == actual_sources)
        for case in run['case_results']:
            for ref in case['source_refs']:
                source = db.get(m.SourceSnapshot, (tenant_id, ref['id']))
                require(source is not None)
                decode(source)
                require(source.payload_sha256 == ref['payload_sha256'])
    if prior['status'] == 'APPROVED_FOR_DEMO':
        from service.domain.evidence import verify_evidence
        require(verify_evidence(history)['historical_integrity'] == 'VALID')
    return history
