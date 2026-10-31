"""Disposable synthetic v1 fixtures, no baseline database access."""
from uuid import uuid4
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from service import models_v1 as m
from service.domain.canonical import canonical_bytes
from service.domain.types import ActorContext, CommandContext
from service.repositories import ZERO, add_payload


def setup(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'v1.db').as_posix())
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    m.BaseV1.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    actors = {name: ActorContext('tenant-a', name, frozenset([role])) for name, role in
              [('analyst', 'ANALYST'), ('reviewer', 'DOMAIN_REVIEWER'), ('approver', 'RELEASE_APPROVER')]}
    ids = {name: str(uuid4()) for name in ('candidate', 'bundle', 'dataset', 'suite', 'evaluator', 'adapter', 'source1', 'source2', 'policy1', 'policy2', 'eligibility')}
    with factory.begin() as db:
        db.add(m.Tenant(id='tenant-a'))
        db.flush()
        db.add(m.TenantAuditHead(tenant_id='tenant-a', sequence=0, head_sha256=ZERO))
        for actor in actors.values():
            db.add(m.Actor(tenant_id=actor.tenant_id, id=actor.actor_id, enabled=True, roles_payload=canonical_bytes(sorted(actor.roles))))
        db.flush()
        source_refs = []
        members = []
        for index in (1, 2):
            source = {'schema': 'source_v1', 'tenant_id': 'tenant-a', 'id': ids[f'source{index}'],
                      'policy_version_id': f'policy-v{index}', 'status': 'APPROVED', 'claim_days': 30}
            row = add_payload(db, m.SourceSnapshot, source)
            source_refs.append({'id': source['id'], 'payload_sha256': row.payload_sha256, 'policy_version_id': source['policy_version_id'], 'status': 'APPROVED'})
            policy = add_payload(db, m.PolicySnapshot, {'schema': 'policy_v1', 'tenant_id': 'tenant-a', 'id': ids[f'policy{index}']})
            members.append({'source_id': source['id'], 'policy_id': policy.id, 'source_sha256': row.payload_sha256, 'policy_sha256': policy.payload_sha256})
        payloads = [(m.CandidateSnapshot, 'candidate', {'model_id': None, 'prompt_id': None, 'adapter_version_id': ids['adapter']}),
            (m.SourceBundle, 'bundle', {'members': members}),
            (m.DatasetSnapshot, 'dataset', {}), (m.SuiteSnapshot, 'suite', {'required_case_ids': ['case-a', 'case-b'],
                'minimum_distinct_policy_versions': 2, 'required_coverage_labels': [], 'case_policy_versions': {'case-a': ['policy-v1'], 'case-b': ['policy-v2']}, 'coverage_by_case': {'case-a': [], 'case-b': []}}),
            (m.EvaluatorSnapshot, 'evaluator', {}), (m.AdapterSnapshot, 'adapter', {'kind': 'fake-deterministic'})]
        for model, name, extra in payloads:
            add_payload(db, model, dict(schema=name + '_v1', tenant_id='tenant-a', id=ids[name], **extra))
        for index in (1, 2):
            db.add(m.SourceBundleMember(tenant_id='tenant-a', source_bundle_id=ids['bundle'], source_id=ids[f'source{index}'], policy_id=ids[f'policy{index}']))
        add_payload(db, m.SourceEligibilitySnapshot, {'schema': 'source_eligibility_v1', 'tenant_id': 'tenant-a',
            'id': ids['eligibility'], 'source_bundle_id': ids['bundle'], 'sequence': 1, 'eligible': True,
            'source_refs': source_refs, 'policy_version_id': 'eligibility-v1'})
    body = {'title': 'Synthetic change', 'pack_version_id': 'pack', 'product_id': 'product', 'workflow': 'claims', 'rule_key': 'days',
        'candidate_snapshot_id': ids['candidate'], 'source_bundle_id': ids['bundle'], 'dataset_version_id': ids['dataset'],
        'suite_version_id': ids['suite'], 'evaluator_version_id': ids['evaluator']}
    return factory, actors, body


def command(body, route='', identity='NEW', revision=None, key=None):
    return CommandContext('POST', '/api/v1/changes' + ('/{change_id}/' + route if route else ''), identity,
                          key or 'test_' + uuid4().hex, revision, body)


def dump(factory):
    with factory() as db:
        return {table.name: sorted([tuple(row) for row in db.execute(select(table))], key=repr)
                for table in m.BaseV1.metadata.tables.values()}




def evaluated(factory, actors, body, claim_days=30):
    from service.commands import execute_command
    created = execute_command(factory, actors['analyst'], command(body))
    identity = created.data['change_id']
    result = execute_command(factory, actors['analyst'], command({'suite_version_id': body['suite_version_id'],
        'case_inputs': [{'case_id': case, 'claim_days': claim_days, 'case_context': {}} for case in ('case-a', 'case-b')]},
        'evaluation-runs', identity, 1))
    return identity, result


def pending_release(factory, actors, body):
    from service.commands import execute_command
    identity, result = evaluated(factory, actors, body)
    execute_command(factory, actors['analyst'], command({}, 'submit', identity, 2))
    execute_command(factory, actors['reviewer'], command({'decision': 'APPROVE', 'reason': 'Domain review accepted'}, 'domain-decision', identity, 3))
    return identity
