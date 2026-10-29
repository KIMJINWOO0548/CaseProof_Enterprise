"""Authoritative transition projection; SQL hashes are not an external trust anchor."""
import json
from sqlalchemy import select
from .models import ChangeTransition, AuditEvent, DecisionNote
from reference.evidence_pack import digest

FIELDS = ('id', 'tenant_id', 'change_id', 'revision_from', 'revision_to', 'from_state',
          'to_state', 'kind', 'actor_id', 'decision_id', 'evidence_hash', 'audit_event_id',
          'occurred_at', 'schema_version')
EDGES = {
    'CHANGE_CREATED': ('NONE', 'DRAFT'),
    'EVALUATION_RECORDED': ('DRAFT', 'DRAFT'),
    'SUBMITTED_FOR_DOMAIN_REVIEW': ('DRAFT', 'PENDING_DOMAIN_REVIEW'),
    'DOMAIN_APPROVE': ('PENDING_DOMAIN_REVIEW', 'PENDING_RELEASE'),
    'DOMAIN_REJECT': ('PENDING_DOMAIN_REVIEW', 'REJECTED'),
    'APPROVED_FOR_DEMO': ('PENDING_RELEASE', 'APPROVED_FOR_DEMO'),
    'RELEASE_REJECT': ('PENDING_RELEASE', 'REJECTED'),
}


def transitions(db, c):
    return db.scalars(select(ChangeTransition).where(ChangeTransition.tenant_id == c.tenant_id,
        ChangeTransition.change_id == c.id).order_by(ChangeTransition.revision_to)).all()


def transition_data(t):
    return {key: getattr(t, key) for key in FIELDS}


def projection_issues(db, c):
    rows = transitions(db, c)
    if not rows:
        return ['LEGACY_UNVERIFIED_TRANSITIONS_MISSING']
    state, revision, domain, release = 'NONE', 0, None, None
    used_notes, used_events, issues = set(), set(), []
    notes = {n.id: n for n in db.scalars(select(DecisionNote).where(
        DecisionNote.tenant_id == c.tenant_id, DecisionNote.change_id == c.id))}
    scoped_events = {}
    try:
        for event in db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == c.tenant_id)):
            body = json.loads(event.event_json)
            if body.get('subject_id') == c.id:
                scoped_events[event.id] = (event, body)
        for t in rows:
            if (t.schema_version != 1 or t.revision_from != revision or t.revision_to != revision + 1
                    or t.from_state != state or EDGES.get(t.kind) != (t.from_state, t.to_state)
                    or (revision == 0) != (t.kind == 'CHANGE_CREATED')):
                issues.append('TRANSITION_SEQUENCE_MISMATCH')
            event, body = scoped_events.get(t.audit_event_id, (None, {}))
            if (not event or t.audit_event_id in used_events or body.get('details', {}).get('transition') != transition_data(t)
                    or body.get('actor_id') != t.actor_id or event.actor_id != t.actor_id
                    or body.get('kind') != t.kind or body.get('at') != t.occurred_at):
                issues.append('TRANSITION_AUDIT_MISMATCH')
            used_events.add(t.audit_event_id)
            if t.kind in ('CHANGE_CREATED', 'EVALUATION_RECORDED', 'SUBMITTED_FOR_DOMAIN_REVIEW'):
                if t.actor_id != c.requester_id or t.decision_id is not None:
                    issues.append('TRANSITION_ACTOR_MISMATCH')
            else:
                note = notes.get(t.decision_id)
                stage = 'DOMAIN' if t.kind.startswith('DOMAIN_') else 'RELEASE'
                decision = 'REJECT' if t.to_state == 'REJECTED' else 'APPROVE'
                if (not note or t.decision_id in used_notes or note.stage != stage or note.decision != decision
                        or note.actor_id != t.actor_id or note.created_at != t.occurred_at
                        or body.get('details', {}).get('decision_id') != t.decision_id
                        or t.actor_id in (c.requester_id, c.owner_id)
                        or (stage == 'RELEASE' and (domain is None or domain == t.actor_id))):
                    issues.append('TRANSITION_DECISION_MISMATCH')
                used_notes.add(t.decision_id)
                if stage == 'DOMAIN':
                    domain = t.actor_id
                else:
                    release = t.actor_id
            if t.kind == 'APPROVED_FOR_DEMO':
                if t.evidence_hash != c.approved_evidence_hash or c.assessment_revision != t.revision_from:
                    issues.append('ASSESSMENT_BINDING_MISMATCH')
                envelope = approval_envelope(t)
                if (json.loads(c.approval_envelope_json or 'null') != envelope
                        or c.approval_envelope_hash != digest(envelope)):
                    issues.append('APPROVAL_ENVELOPE_MISMATCH')
            elif t.evidence_hash is not None:
                issues.append('UNEXPECTED_EVIDENCE_HASH')
            state, revision = t.to_state, t.revision_to
        if used_notes != set(notes) or used_events != set(scoped_events):
            issues.append('TRANSITION_RECORD_SET_MISMATCH')
        if (state, revision, domain, release) != (c.status, c.revision, c.domain_reviewer_id, c.release_approver_id):
            issues.append('CHANGE_PROJECTION_MISMATCH')
        if state != 'APPROVED_FOR_DEMO' and any((c.approved_evidence_hash, c.assessment_revision,
                                                c.approval_envelope_json, c.approval_envelope_hash)):
            issues.append('UNEXPECTED_APPROVAL_SNAPSHOT')
    except (ValueError, TypeError, KeyError, AttributeError):
        issues.append('TRANSITION_RECORD_INVALID')
    return issues


def approval_envelope(t):
    return {'schema': 'approval_envelope_v1', 'tenant_id': t.tenant_id, 'change_id': t.change_id,
            'assessment_sha256': t.evidence_hash, 'decision_id': t.decision_id,
            'event_id': t.audit_event_id, 'transition_id': t.id, 'approver_id': t.actor_id,
            'approved_at': t.occurred_at, 'revision': t.revision_to}
