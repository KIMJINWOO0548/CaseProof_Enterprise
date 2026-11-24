"""Read-only, tenant-authorized projection for the decision workbench."""
from service.api.errors import DomainError
from service.api.schemas_v1 import MAX_REVISION
from service.commands import authorize, current_approval_gate, require_approval_gate, require_workflow_state
from service.domain.evidence import verify_evidence
from service.repositories import get_change, load_history, require


ACTIONS = {
    'evaluate': 'EVALUATION_RECORDED',
    'submit': 'SUBMITTED_FOR_DOMAIN_REVIEW',
    'domain_approve': 'DOMAIN_APPROVE',
    'domain_reject': 'DOMAIN_REJECT',
    'release_approve': 'APPROVED_FOR_DEMO',
    'release_reject': 'RELEASE_REJECT',
}
DECISION_FIELDS = ('id', 'stage', 'decision', 'actor_id', 'input_revision', 'output_revision', 'reason', 'occurred_at')
SOURCE_FIELDS = ('id', 'policy_version_id', 'payload_sha256', 'status')


def _action(kind, actor, change, snapshot, gate):
    try:
        authorize(actor, kind, change)
        require_workflow_state(kind, snapshot)
        require(snapshot['revision'] < MAX_REVISION, 'INVALID_REQUEST')
        if kind in ('SUBMITTED_FOR_DOMAIN_REVIEW', 'APPROVED_FOR_DEMO'):
            require_approval_gate(gate)
    except DomainError as error:
        return {'allowed': False, 'reason': error.code}
    return {'allowed': True, 'reason': None}


def _approved_seal(history, approved_revision):
    if approved_revision is None:
        return None
    assessment, envelope = history['assessment'], history['envelope']
    run = next(run for run in history['runs'] if run['id'] == assessment['selected_run_id'])
    eligibility = next(snapshot for snapshot in history['refs']['source_eligibility']
                       if snapshot['id'] == assessment['source_eligibility_snapshot_ref']['id'])
    return {
        'approved_revision': approved_revision,
        'preapproval_revision': assessment['preapproval_revision'],
        'run_id': run['id'],
        'run_config_sha256': run['run_config_sha256'],
        'assessment_sha256': envelope['assessment_sha256'],
        'source_bundle_id': assessment['source_bundle_ref']['id'],
        'source_eligibility_snapshot_id': eligibility['id'],
        'decision_id': envelope['release_decision_ref']['id'],
        'sources': [{field: source[field] for field in SOURCE_FIELDS} for source in eligibility['source_refs']],
    }


def _invalid_review(change, code):
    return {
        'change_id': change.id,
        'revision': change.revision,
        'status': 'INTEGRITY_INVALID',
        'historical_integrity': 'LEGACY_UNVERIFIED' if code == 'EXECUTION_CONFIG_UNVERIFIED' else 'INVALID',
        'current_approval_eligibility': 'BLOCKED',
        'external_anchor': 'NOT_CONFIGURED',
        'approved_revision': None,
        'envelope_sha256': None,
        'evaluation': None,
        'actions': {name: {'allowed': False, 'reason': code} for name in ACTIONS},
        'decisions': [],
        'seal': None,
    }


def read_review(db, actor, change_id):
    """Use the validated snapshot and actual action checks. A read never authorizes a subsequent write."""
    change = get_change(db, actor.tenant_id, change_id)
    try:
        history = load_history(db, actor.tenant_id, change_id)
        evidence = verify_evidence(history)
        require(evidence['historical_integrity'] == 'VALID')
        gate = current_approval_gate(history)
    except DomainError as error:
        return _invalid_review(change, error.code)

    snapshot = history['snapshot']
    evaluation = None
    if gate is not None:
        run = history['runs'][-1]
        evaluation = {field: run[field] for field in ('recorded_revision', 'run_config_sha256', 'completion', 'gate_summary')}
        evaluation.update(run_id=run['id'], current_gate_summary=gate['gate_summary'], gate_reasons=gate['reasons'])
    return {
        'change_id': change_id,
        'revision': snapshot['revision'],
        'status': snapshot['status'],
        **evidence,
        'evaluation': evaluation,
        'actions': {name: _action(kind, actor, change, snapshot, gate) for name, kind in ACTIONS.items()},
        'decisions': [{field: note[field] for field in DECISION_FIELDS} for note in history['decisions']],
        'seal': _approved_seal(history, evidence['approved_revision']),
    }
