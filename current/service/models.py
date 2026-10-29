"""Relational schema for the synthetic CaseProof v5 demonstration.
Every reference between tenant-scoped records uses composite foreign keys.
"""
from __future__ import annotations
from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, Text

class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = 'tenants'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    audit_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audit_head: Mapped[str] = mapped_column(String(64), default='0'*64, nullable=False)

class User(Base):
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('id','tenant_id'),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    roles_json: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

class PolicyRule(Base):
    __tablename__ = 'policy_rules'
    __table_args__ = (UniqueConstraint('id','tenant_id'),)
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

class Change(Base):
    __tablename__ = 'changes'
    __table_args__ = (
        UniqueConstraint('id','tenant_id'),
        ForeignKeyConstraint(['tenant_id','requester_id'],['users.tenant_id','users.id']),
        ForeignKeyConstraint(['tenant_id','owner_id'],['users.tenant_id','users.id']),
        ForeignKeyConstraint(['tenant_id','domain_reviewer_id'],['users.tenant_id','users.id']),
        ForeignKeyConstraint(['tenant_id','release_approver_id'],['users.tenant_id','users.id']),
        CheckConstraint('revision >= 1',name='ck_revision_positive'),
    )
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    product: Mapped[str] = mapped_column(String(80), nullable=False)
    workflow: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(80), nullable=False)
    domain_reviewer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    release_approver_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default='DRAFT', nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluator_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assessment_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_envelope_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_envelope_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

class Evaluation(Base):
    __tablename__ = 'evaluations'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id','change_id'],['changes.tenant_id','changes.id']),
        ForeignKeyConstraint(['tenant_id','actor_id'],['users.tenant_id','users.id']),
        UniqueConstraint('tenant_id','change_id','idempotency_key',name='uq_eval_idempotency'),
    )
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    change_id: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    __table_args__ = (
        UniqueConstraint('tenant_id','id'),
        UniqueConstraint('tenant_id','sequence'),
        ForeignKeyConstraint(['tenant_id','actor_id'],['users.tenant_id','users.id']),
    )
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class DecisionNote(Base):
    __tablename__ = 'decision_notes'
    __table_args__ = (
        UniqueConstraint('tenant_id','change_id','id'),
        ForeignKeyConstraint(['tenant_id','change_id'],['changes.tenant_id','changes.id']),
        ForeignKeyConstraint(['tenant_id','actor_id'],['users.tenant_id','users.id']),
    )
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey('tenants.id'), nullable=False)
    change_id: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class ChangeTransition(Base):
    __tablename__ = 'change_transitions'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'change_id', 'revision_to'),
        UniqueConstraint('tenant_id', 'audit_event_id'),
        ForeignKeyConstraint(['tenant_id','change_id'], ['changes.tenant_id','changes.id']),
        ForeignKeyConstraint(['tenant_id','actor_id'], ['users.tenant_id','users.id']),
        ForeignKeyConstraint(['tenant_id','change_id','decision_id'],
                             ['decision_notes.tenant_id','decision_notes.change_id','decision_notes.id']),
        ForeignKeyConstraint(['tenant_id','audit_event_id'], ['audit_events.tenant_id','audit_events.id']),
        CheckConstraint('revision_from >= 0 AND revision_to = revision_from + 1'),
        CheckConstraint("(kind = 'CHANGE_CREATED' AND from_state = 'NONE' AND to_state = 'DRAFT' AND revision_from = 0) OR "
                        "(kind = 'EVALUATION_RECORDED' AND from_state = 'DRAFT' AND to_state = 'DRAFT') OR "
                        "(kind = 'SUBMITTED_FOR_DOMAIN_REVIEW' AND from_state = 'DRAFT' AND to_state = 'PENDING_DOMAIN_REVIEW') OR "
                        "(kind = 'DOMAIN_APPROVE' AND from_state = 'PENDING_DOMAIN_REVIEW' AND to_state = 'PENDING_RELEASE') OR "
                        "(kind = 'DOMAIN_REJECT' AND from_state = 'PENDING_DOMAIN_REVIEW' AND to_state = 'REJECTED') OR "
                        "(kind = 'APPROVED_FOR_DEMO' AND from_state = 'PENDING_RELEASE' AND to_state = 'APPROVED_FOR_DEMO') OR "
                        "(kind = 'RELEASE_REJECT' AND from_state = 'PENDING_RELEASE' AND to_state = 'REJECTED')"),
    )
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False)
    change_id: Mapped[str] = mapped_column(String(50), nullable=False)
    revision_from: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_to: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str] = mapped_column(String(40), nullable=False)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_event_id: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
