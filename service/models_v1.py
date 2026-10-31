"""Isolated v1 persistence. Payload/history validation belongs to the command layer.

Use migrations for disposable databases; importing this module never opens a DB.
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DDL, ForeignKeyConstraint,
    LargeBinary, MetaData, String, Table, UniqueConstraint, event,
)
from sqlalchemy.orm import DeclarativeBase

MAX_INTEGER = 9_007_199_254_740_991


class BaseV1(DeclarativeBase):
    metadata = MetaData(naming_convention={
        'ix': 'ix_%(table_name)s_%(column_0_name)s',
        'uq': 'uq_%(table_name)s_%(column_0_N_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    })


def text(name, *, nullable=False, primary_key=False):
    return Column(name, String, nullable=nullable, primary_key=primary_key)


def integer(name, *, nullable=False, primary_key=False):
    return Column(name, BigInteger, nullable=nullable, primary_key=primary_key)


def bound(name, minimum=1):
    return CheckConstraint(f"typeof({name}) = 'integer' AND {name} BETWEEN {minimum} AND {MAX_INTEGER}", name=f'{name}_range')


def ref(column, target, target_column='id'):
    return ForeignKeyConstraint(
        ['tenant_id', column], [f'v1_{target}.tenant_id', f'v1_{target}.{target_column}'],
        deferrable=True, initially='DEFERRED',
    )


def revision_ref(column):
    return ForeignKeyConstraint(
        ['tenant_id', 'change_id', column],
        ['v1_change_revision.tenant_id', 'v1_change_revision.change_id', 'v1_change_revision.revision'],
        deferrable=True, initially='DEFERRED',
    )


def payload():
    return [text('schema_version'), Column('canonical_payload', LargeBinary, nullable=False),
            text('payload_sha256'),
            CheckConstraint('length(schema_version) > 0', name='schema_nonempty'),
            CheckConstraint('length(canonical_payload) > 0', name='payload_nonempty'),
            CheckConstraint("length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'", name='hash_hex')]


def table(name, *columns, immutable=True, identity=True):
    items = [text('tenant_id', primary_key=True)]
    if identity:
        items.append(text('id', primary_key=True))
    items.extend(columns)
    items.append(ForeignKeyConstraint(['tenant_id'], ['v1_tenant.id']))
    result = Table('v1_' + name, BaseV1.metadata, *items, info={'immutable': immutable})
    return result


class Tenant(BaseV1):
    __table__ = Table('v1_tenant', BaseV1.metadata, text('id', primary_key=True))


class Actor(BaseV1):
    __table__ = table('actor', Column('enabled', Boolean, nullable=False),
                      Column('roles_payload', LargeBinary, nullable=False), immutable=False)


class TenantAuditHead(BaseV1):
    __table__ = table('tenant_audit_head', integer('sequence'), text('head_sha256'),
                      UniqueConstraint('tenant_id'), bound('sequence', 0),
                      CheckConstraint("length(head_sha256) = 64 AND head_sha256 NOT GLOB '*[^0-9a-f]*'", name='head_hex'),
                      identity=False, immutable=False)
    __mapper_args__ = {'primary_key': [__table__.c.tenant_id]}


class SourceSnapshot(BaseV1):
    __table__ = table('source_snapshot', *payload())


class PolicySnapshot(BaseV1):
    __table__ = table('policy_snapshot', *payload())


class ModelSnapshot(BaseV1):
    __table__ = table('model_snapshot', *payload())


class PromptSnapshot(BaseV1):
    __table__ = table('prompt_snapshot', *payload())


class CandidateSnapshot(BaseV1):
    __table__ = table('candidate_snapshot', text('model_id', nullable=True), text('prompt_id', nullable=True),
                      ref('model_id', 'model_snapshot'), ref('prompt_id', 'prompt_snapshot'), *payload())


class SourceBundle(BaseV1):
    __table__ = table('source_bundle', *payload())


class SourceBundleMember(BaseV1):
    __table__ = table('source_bundle_member', text('source_bundle_id', primary_key=True),
                      text('source_id', primary_key=True), text('policy_id', primary_key=True),
                      ref('source_bundle_id', 'source_bundle'), ref('source_id', 'source_snapshot'),
                      ref('policy_id', 'policy_snapshot'), identity=False)
    __mapper_args__ = {'primary_key': list(__table__.c)}


class DatasetSnapshot(BaseV1):
    __table__ = table('dataset_snapshot', *payload())


class SuiteSnapshot(BaseV1):
    __table__ = table('suite_snapshot', *payload())


class EvaluatorSnapshot(BaseV1):
    __table__ = table('evaluator_snapshot', *payload())


class AdapterSnapshot(BaseV1):
    __table__ = table('adapter_snapshot', *payload())


class SourceEligibilitySnapshot(BaseV1):
    __table__ = table('source_eligibility_snapshot', text('source_bundle_id'),
                      ref('source_bundle_id', 'source_bundle'), *payload())


def snapshot_refs():
    pairs = [('candidate_snapshot_id', 'candidate_snapshot'), ('source_bundle_id', 'source_bundle'),
             ('dataset_version_id', 'dataset_snapshot'), ('suite_version_id', 'suite_snapshot'),
             ('evaluator_version_id', 'evaluator_snapshot')]
    return [item for column, target in pairs for item in (text(column), ref(column, target))]


def change_refs():
    return [text('requester_id'), text('owner_id'), text('domain_reviewer_id', nullable=True),
            text('release_approver_id', nullable=True), text('parent_change_id', nullable=True),
            text('active_run_id', nullable=True), text('assessment_sha256', nullable=True),
            ref('requester_id', 'actor'), ref('owner_id', 'actor'), ref('domain_reviewer_id', 'actor'),
            ref('release_approver_id', 'actor'), ref('parent_change_id', 'change'),
            ref('active_run_id', 'evaluation_run'), ref('assessment_sha256', 'assessment', 'payload_sha256'),
            *snapshot_refs()]


class Change(BaseV1):
    # No latest-revision FK: G1.3 must verify the projection before each mutation.
    __table__ = table('change', integer('revision'), text('status'),
                      text('approval_envelope_sha256', nullable=True), *change_refs(),
                      bound('revision', 0),
                      CheckConstraint("(revision = 0 AND status = 'INCOMPLETE') OR "
                                      "(revision > 0 AND status IN ('DRAFT','PENDING_DOMAIN_REVIEW',"
                                      "'PENDING_RELEASE','REJECTED','APPROVED_FOR_DEMO'))", name='projection_state'),
                      ref('approval_envelope_sha256', 'approval_envelope', 'payload_sha256'), immutable=False)


class ChangeRevision(BaseV1):
    __table__ = table('change_revision', text('change_id', primary_key=True),
                      integer('revision', primary_key=True), *change_refs(), *payload(),
                      ref('change_id', 'change'), bound('revision'), identity=False,
                      )
    __mapper_args__ = {'primary_key': [__table__.c.tenant_id, __table__.c.change_id, __table__.c.revision]}


class EvaluationRun(BaseV1):
    __table__ = table('evaluation_run', text('change_id'), integer('recorded_revision'), text('actor_id'),
                      text('adapter_version_id'), *snapshot_refs(), *payload(),
                      ref('change_id', 'change'), ref('actor_id', 'actor'), ref('adapter_version_id', 'adapter_snapshot'),
                      revision_ref('recorded_revision'), bound('recorded_revision'),
                      UniqueConstraint('tenant_id', 'change_id', 'recorded_revision'))


class DecisionNote(BaseV1):
    __table__ = table('decision_note', text('change_id'), text('stage'), text('actor_id'),
                      integer('input_revision'), integer('output_revision'), text('assessment_sha256', nullable=True),
                      *payload(), ref('change_id', 'change'), ref('actor_id', 'actor'),
                      revision_ref('input_revision'), revision_ref('output_revision'),
                      ref('assessment_sha256', 'assessment', 'payload_sha256'),
                      bound('input_revision'), bound('output_revision'),
                      CheckConstraint('output_revision = input_revision + 1', name='next_revision'),
                      CheckConstraint("stage IN ('DOMAIN','RELEASE')", name='stage'),
                      UniqueConstraint('tenant_id', 'change_id', 'stage'))


class ChangeTransition(BaseV1):
    __table__ = table('change_transition', text('change_id'), integer('revision_from'), integer('revision_to'),
                      text('actor_id'), text('evaluation_run_id', nullable=True), text('decision_id', nullable=True),
                      text('assessment_sha256', nullable=True), *payload(), ref('change_id', 'change'),
                      ref('actor_id', 'actor'), ref('evaluation_run_id', 'evaluation_run'), ref('decision_id', 'decision_note'),
                      ref('assessment_sha256', 'assessment', 'payload_sha256'), revision_ref('revision_to'),
                      bound('revision_from', 0), bound('revision_to'),
                      CheckConstraint('revision_to = revision_from + 1', name='next_revision'),
                      UniqueConstraint('tenant_id', 'change_id', 'revision_to'))


class AuditEvent(BaseV1):
    __table__ = table('audit_event', integer('sequence'), text('actor_id'), text('subject_id'), text('transition_id'),
                      *payload(), bound('sequence'), ref('actor_id', 'actor'), ref('subject_id', 'change'),
                      ref('transition_id', 'change_transition'), UniqueConstraint('tenant_id', 'sequence'),
                      UniqueConstraint('tenant_id', 'transition_id'))


class Assessment(BaseV1):
    __table__ = table('assessment', text('change_id'), integer('preapproval_revision'), text('selected_run_id'),
                      text('source_eligibility_snapshot_id'), text('model_id', nullable=True), text('prompt_id', nullable=True),
                      *snapshot_refs(), *payload(), ref('change_id', 'change'), revision_ref('preapproval_revision'),
                      ref('selected_run_id', 'evaluation_run'), ref('source_eligibility_snapshot_id', 'source_eligibility_snapshot'),
                      ref('model_id', 'model_snapshot'), ref('prompt_id', 'prompt_snapshot'), bound('preapproval_revision'),
                      UniqueConstraint('tenant_id', 'change_id'), UniqueConstraint('tenant_id', 'payload_sha256'))


class ApprovalEnvelope(BaseV1):
    __table__ = table('approval_envelope', text('change_id'), integer('preapproval_revision'), integer('approved_revision'),
                      text('assessment_sha256'), text('release_decision_id'), text('release_transition_id'),
                      text('release_event_id'), text('approver_id'), *payload(), ref('change_id', 'change'),
                      revision_ref('preapproval_revision'), revision_ref('approved_revision'),
                      ref('assessment_sha256', 'assessment', 'payload_sha256'), ref('release_decision_id', 'decision_note'),
                      ref('release_transition_id', 'change_transition'), ref('release_event_id', 'audit_event'),
                      ref('approver_id', 'actor'), bound('preapproval_revision'), bound('approved_revision'),
                      CheckConstraint('approved_revision = preapproval_revision + 1', name='next_revision'),
                      UniqueConstraint('tenant_id', 'change_id'), UniqueConstraint('tenant_id', 'payload_sha256'))


class IdempotencyRecord(BaseV1):
    __table__ = table('idempotency_record', text('actor_id'), text('key'), text('change_id'), integer('result_revision'),
                      integer('original_status'), text('fingerprint_sha256'), *payload(),
                      ref('actor_id', 'actor'), ref('change_id', 'change'), revision_ref('result_revision'),
                      bound('result_revision'), CheckConstraint('original_status BETWEEN 200 AND 299', name='success_status'),
                      UniqueConstraint('tenant_id', 'actor_id', 'key'))


# Array references remain in canonical bytes; these rows provide tenant FK enforcement.
class AssessmentRunRef(BaseV1):
    __table__ = table('assessment_run_ref', text('assessment_id'), text('run_id'),
                      ref('assessment_id', 'assessment'), ref('run_id', 'evaluation_run'),
                      UniqueConstraint('tenant_id', 'assessment_id', 'run_id'))


class AssessmentDecisionRef(BaseV1):
    __table__ = table('assessment_decision_ref', text('assessment_id'), text('decision_id'),
                      ref('assessment_id', 'assessment'), ref('decision_id', 'decision_note'),
                      UniqueConstraint('tenant_id', 'assessment_id', 'decision_id'))


class AssessmentTransitionRef(BaseV1):
    __table__ = table('assessment_transition_ref', text('assessment_id'), text('transition_id'), text('event_id'),
                      ref('assessment_id', 'assessment'), ref('transition_id', 'change_transition'),
                      ref('event_id', 'audit_event'), UniqueConstraint('tenant_id', 'assessment_id', 'transition_id'))


class RunSourceRef(BaseV1):
    __table__ = table('run_source_ref', text('run_id'), text('source_id'), text('case_id'),
                      ref('run_id', 'evaluation_run'), ref('source_id', 'source_snapshot'),
                      UniqueConstraint('tenant_id', 'run_id', 'case_id', 'source_id'))


IMMUTABLE_TABLES = tuple(t.name for t in BaseV1.metadata.tables.values() if t.info.get('immutable'))
for _table in BaseV1.metadata.tables.values():
    operations = ('UPDATE', 'DELETE') if _table.name in IMMUTABLE_TABLES else (('DELETE',) if _table.name == 'v1_change' else ())
    for _operation in operations:
        event.listen(_table, 'after_create', DDL(
            f'CREATE TRIGGER {_table.name}_no_{_operation.lower()} BEFORE {_operation} ON {_table.name} '
            "BEGIN SELECT RAISE(ABORT, 'v1 append-only record'); END"
        ).execute_if(dialect='sqlite'))


    if operations:
        # OR REPLACE can delete without firing DELETE triggers in default SQLite.
        keys = [_table.primary_key] + [c for c in _table.constraints if isinstance(c, UniqueConstraint)]
        collisions = ['(' + ' AND '.join(f'{c.name} = NEW.{c.name}' for c in key.columns) + ')' for key in keys]
        event.listen(_table, 'after_create', DDL(
            f'CREATE TRIGGER {_table.name}_no_replace BEFORE INSERT ON {_table.name} '
            f"WHEN EXISTS (SELECT 1 FROM {_table.name} WHERE {' OR '.join(collisions)}) "
            "BEGIN SELECT RAISE(ABORT, 'v1 append-only record'); END"
        ).execute_if(dialect='sqlite'))
