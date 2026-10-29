"""CaseProof v4: deterministic synthetic governance reference.

This is NOT an authentication provider, audit database, or production insurance
approval engine. Authentication/tenant membership are supplied by a trusted
server-side boundary, never by a web request body.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class Actor:
    user_id: str
    tenant_id: str
    roles: FrozenSet[str]
    enabled: bool = True


@dataclass(frozen=True)
class DecisionContext:
    tenant_id: str
    requester_id: str
    owner_id: str
    expected_revision: int
    actual_revision: int
    source_approved: bool
    evidence_verified: bool
    critical_findings: int
    mandatory_incomplete: int
    pending_domain_reviews: int
    review_state: str
    release_state: str
    kill_switch: bool = False


ROLE_ACTIONS = {
    'VIEWER': {'read'},
    'ANALYST': {'read', 'submit_review'},
    'DOMAIN_REVIEWER': {'read', 'domain_approve', 'domain_reject'},
    'AI_RISK_OFFICER': {'read', 'risk_approve', 'risk_reject'},
    'RELEASE_APPROVER': {'read', 'release_approve', 'release_reject'},
    'AUDITOR': {'read', 'export_redacted_evidence'},
    'TENANT_ADMIN': {'read', 'manage_membership'},
}


def authorize(actor: Actor, subject_tenant: str, action: str) -> tuple[bool, str]:
    """Fail-closed authorization. Caller must be authenticated by backend."""
    if not actor.enabled or not actor.user_id or not actor.tenant_id:
        return False, 'ACTOR_DISABLED_OR_INVALID'
    if not subject_tenant or actor.tenant_id != subject_tenant:
        return False, 'TENANT_MISMATCH'
    granted = set().union(*(ROLE_ACTIONS.get(role, set()) for role in actor.roles))
    if action not in granted:
        return False, 'PERMISSION_DENIED'
    return True, 'AUTHORIZED'


def decide_release(actor: Actor, ctx: DecisionContext) -> dict:
    """One-shot release decision; real service needs transaction + DB locks."""
    ok, code = authorize(actor, ctx.tenant_id, 'release_approve')
    if not ok:
        return {'status': 'BLOCKED', 'reasons': [code]}
    blocks = []
    reviews = []
    if actor.user_id in {ctx.requester_id, ctx.owner_id}:
        blocks.append('SEPARATION_OF_DUTIES')
    if ctx.expected_revision != ctx.actual_revision:
        blocks.append('STALE_REVISION')
    if ctx.release_state != 'PENDING_APPROVAL':
        blocks.append('INVALID_RELEASE_STATE')
    if ctx.review_state != 'DOMAIN_APPROVED':
        blocks.append('DOMAIN_REVIEW_NOT_APPROVED')
    if not ctx.source_approved:
        blocks.append('SOURCE_NOT_APPROVED')
    if not ctx.evidence_verified:
        blocks.append('EVIDENCE_INTEGRITY_FAILURE')
    if ctx.kill_switch:
        blocks.append('KILL_SWITCH_ACTIVE')
    if ctx.critical_findings != 0:
        blocks.append('CRITICAL_FINDINGS_PRESENT')
    if ctx.mandatory_incomplete != 0:
        blocks.append('MANDATORY_TEST_INCOMPLETE')
    if ctx.pending_domain_reviews != 0:
        reviews.append('PENDING_DOMAIN_REVIEW')
    status = 'BLOCKED' if blocks else ('PENDING_APPROVAL' if reviews else 'APPROVED_FOR_DEMO')
    return {'status': status, 'reasons': blocks + reviews}
