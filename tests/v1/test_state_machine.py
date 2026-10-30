"""Independent target state table and identity rules; no DB or HTTP integration."""
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from service.api.errors import DomainError
from service.domain.canonical import content_hash
from service.domain.state_machine import TransitionChecks, apply_transition
from service.domain.types import ActorContext

ROOT = Path(__file__).resolve().parents[2]
TIME = '2026-10-29T03:34:56.123456Z'
REQUESTER = ActorContext('synthetic-tenant-a', 'synthetic-requester', {'ANALYST'})
REVIEWER = ActorContext(REQUESTER.tenant_id, 'synthetic-reviewer', {'DOMAIN_REVIEWER'})
APPROVER = ActorContext(REQUESTER.tenant_id, 'synthetic-approver', {'RELEASE_APPROVER'})


def load(name):
    return json.loads((ROOT / 'contracts/examples' / f'{name}.json').read_text(encoding='utf-8'))


def checks(snapshot, **kwargs):
    return TransitionChecks(tenant_id=REQUESTER.tenant_id, change_id=load('snapshot-genesis')['change_id'],
                            revision=snapshot['revision'] if snapshot else 0,
                            snapshot_sha256=content_hash('change-revision', snapshot) if snapshot else None, **kwargs)


def command(snapshot, kind, **kwargs):
    body = {}
    if 'note' in kwargs:
        body = {key: kwargs['note'][key] for key in ('decision', 'reason')}
    elif kind == 'EVALUATION_RECORDED':
        body = load('evaluation-valid')
    return dict(kind=kind, change_id=load('snapshot-genesis')['change_id'], occurred_at=TIME,
                expected_revision=snapshot['revision'] if snapshot else None,
                body=body, checks=checks(snapshot), **kwargs)


def note(snapshot, stage, decision, actor, assessment=None):
    value = load('decision-note-domain')
    value.update(stage=stage, decision=decision, actor_id=actor.actor_id,
                 input_revision=snapshot['revision'], output_revision=snapshot['revision'] + 1,
                 assessment_sha256=assessment)
    if stage == 'RELEASE':
        value['id'] = '00000000-0000-4000-8000-000000000016'
    return value


def path_to_release():
    created = command(None, 'CHANGE_CREATED')
    created['body'] = load('create-minimal')
    draft = apply_transition(None, created, REQUESTER)
    run = load('run-complete')
    run.update(recorded_revision=2, actor_id=REQUESTER.actor_id)
    evaluated = apply_transition(draft, command(draft, 'EVALUATION_RECORDED', run=run), REQUESTER)
    submitted_command = command(evaluated, 'SUBMITTED_FOR_DOMAIN_REVIEW', run=run)
    submitted_command['checks'] = checks(evaluated, gate_run_sha256=content_hash('evaluation-run', run))
    submitted = apply_transition(evaluated, submitted_command, REQUESTER)
    domain = note(submitted, 'DOMAIN', 'APPROVE', REVIEWER)
    pending = apply_transition(submitted, command(submitted, 'DOMAIN_APPROVE', note=domain), REVIEWER)
    return draft, evaluated, submitted, pending, run, domain


def test_revision_and_actor_rules_and_input_immutability():
    draft, evaluated, submitted, pending, run, domain = path_to_release()
    assert [x['revision'] for x in (draft, evaluated, submitted, pending)] == [1, 2, 3, 4]
    assert draft['requester_id'] == draft['owner_id'] == REQUESTER.actor_id
    assert draft['active_run_id'] is None
    assert evaluated['active_run_id'] == submitted['active_run_id'] == pending['active_run_id'] == run['id']
    approval = command(pending, 'APPROVED_FOR_DEMO', run=run, domain_note=domain,
                       note=note(pending, 'RELEASE', 'APPROVE', APPROVER, 'a'*64))
    approval['checks'] = checks(pending, gate_run_sha256=content_hash('evaluation-run', run),
                                source_bundle_id=pending['source_bundle_id'], source_eligible=True,
                                assessment_sha256='a'*64)
    before = copy.deepcopy(pending)
    accepted = apply_transition(pending, approval, APPROVER)
    assert accepted == apply_transition(pending, approval, APPROVER)
    assert pending == before and accepted is not pending
    assert accepted['status'] == 'APPROVED_FOR_DEMO' and accepted['revision'] == 5
    assert accepted['assessment_sha256'] == 'a'*64
    mutable = {'revision', 'status', 'domain_reviewer_id', 'release_approver_id', 'active_run_id', 'assessment_sha256', 'updated_at'}
    assert {k: v for k, v in draft.items() if k not in mutable} == {k: v for k, v in accepted.items() if k not in mutable}


@pytest.mark.parametrize('stage', ['DOMAIN', 'RELEASE'])
def test_reject_paths_have_note_and_revision(stage):
    _, _, submitted, pending, _, domain = path_to_release()
    snapshot, actor, kind = (submitted, REVIEWER, 'DOMAIN_REJECT') if stage == 'DOMAIN' else (pending, APPROVER, 'RELEASE_REJECT')
    body = command(snapshot, kind, note=note(snapshot, stage, 'REJECT', actor))
    if stage == 'RELEASE':
        body['domain_note'] = domain
    rejected = apply_transition(snapshot, body, actor)
    assert rejected['status'] == 'REJECTED' and rejected['revision'] == snapshot['revision'] + 1
    assert rejected['assessment_sha256'] is None


TABLE = json.loads((ROOT / 'contracts/state-machine.json').read_text(encoding='utf-8'))
ILLEGAL = [(kind['kind'], state) for kind in TABLE['transitions']
           for state in ['NONE'] + TABLE['states'] if kind['from_state'] != state]


@pytest.mark.parametrize('kind,state', ILLEGAL)
def test_all_illegal_state_kind_combinations(kind, state):
    snapshot = None if state == 'NONE' else load('snapshot-genesis')
    if snapshot:
        snapshot['status'] = state
        if state in ('PENDING_DOMAIN_REVIEW', 'PENDING_RELEASE', 'APPROVED_FOR_DEMO'):
            snapshot['active_run_id'] = load('run-complete')['id']
        if state in ('PENDING_RELEASE', 'APPROVED_FOR_DEMO'):
            snapshot['domain_reviewer_id'] = REVIEWER.actor_id
        if state == 'APPROVED_FOR_DEMO':
            snapshot['release_approver_id'] = APPROVER.actor_id
            snapshot['assessment_sha256'] = 'a'*64
    with pytest.raises(DomainError) as exc:
        apply_transition(snapshot, command(snapshot, kind), REQUESTER)
    assert exc.value.code == 'INVALID_STATUS'


@pytest.mark.parametrize('mutation,code', [('stale','STALE_REVISION'), ('tenant','NOT_FOUND'), ('role','FORBIDDEN'),
                                         ('requester','REQUESTER_ONLY'), ('binding','EVIDENCE_RECORD_TAMPERED')])
def test_common_guards_fail_closed(mutation, code):
    draft, _, _, _, run, _ = path_to_release()
    actor = REQUESTER
    body = command(draft, 'EVALUATION_RECORDED', run=run)
    if mutation == 'stale': body['expected_revision'] = 2
    if mutation == 'tenant': actor = ActorContext('tenant-b', REQUESTER.actor_id, REQUESTER.roles)
    if mutation == 'role': actor = ActorContext(REQUESTER.tenant_id, REQUESTER.actor_id, {'DOMAIN_REVIEWER'})
    if mutation == 'requester': actor = ActorContext(REQUESTER.tenant_id, 'someone-else', {'ANALYST'})
    if mutation == 'binding': body['checks'] = replace(body['checks'], snapshot_sha256='0'*64)
    with pytest.raises(DomainError) as exc:
        apply_transition(draft, body, actor)
    assert exc.value.code == code


@pytest.mark.parametrize('stage', ['DOMAIN', 'RELEASE'])
def test_multirole_self_approval_denied(stage):
    _, _, submitted, pending, _, domain = path_to_release()
    snapshot = submitted if stage == 'DOMAIN' else pending
    actor = ActorContext(REQUESTER.tenant_id, REQUESTER.actor_id, {'ANALYST', 'DOMAIN_REVIEWER', 'RELEASE_APPROVER'})
    body = command(snapshot, 'DOMAIN_REJECT' if stage == 'DOMAIN' else 'RELEASE_REJECT', note=note(snapshot, stage, 'REJECT', actor))
    if stage == 'RELEASE': body['domain_note'] = domain
    with pytest.raises(DomainError) as exc:
        apply_transition(snapshot, body, actor)
    assert exc.value.code == 'SEPARATION_OF_DUTIES'
    if stage == 'RELEASE':
        actor = ActorContext(REVIEWER.tenant_id, REVIEWER.actor_id, {'RELEASE_APPROVER'})
        body['note'] = note(snapshot, stage, 'REJECT', actor)
        with pytest.raises(DomainError) as exc:
            apply_transition(snapshot, body, actor)
        assert exc.value.code == 'SEPARATION_OF_DUTIES'


@pytest.mark.parametrize('field,value', [('actor_id','someone-else'), ('stage','RELEASE'), ('decision','REJECT'),
                                       ('input_revision',2), ('output_revision',9), ('reason','  Synthetic evidence reviewed.  ')])
def test_missing_or_mismatched_decision_rejected(field, value):
    _, _, submitted, _, _, _ = path_to_release()
    body = command(submitted, 'DOMAIN_APPROVE')
    with pytest.raises((DomainError, ValueError)):
        apply_transition(submitted, body, REVIEWER)
    body['note'] = note(submitted, 'DOMAIN', 'APPROVE', REVIEWER)
    body['note'][field] = value
    with pytest.raises((DomainError, ValueError)):
        apply_transition(submitted, body, REVIEWER)


def test_old_pass_and_unbound_gate_do_not_authorize_submit():
    _, evaluated, _, _, run, _ = path_to_release()
    body = command(evaluated, 'SUBMITTED_FOR_DOMAIN_REVIEW', run=run)
    with pytest.raises(DomainError):
        apply_transition(evaluated, body, REQUESTER)
    body['checks'] = checks(evaluated, gate_run_sha256=content_hash('evaluation-run', run))
    body['run']['id'] = '00000000-0000-4000-8000-000000000099'
    with pytest.raises(DomainError):
        apply_transition(evaluated, body, REQUESTER)


def test_untyped_client_checks_and_unrecognized_kind_are_rejected():
    body = command(None, 'CHANGE_CREATED')
    body['body'] = load('create-minimal')
    body['checks'] = {'source_eligible': True, 'integrity_valid': True}
    with pytest.raises((DomainError, ValueError, TypeError)):
        apply_transition(None, body, REQUESTER)


@pytest.mark.parametrize('mutation', ['run', 'domain_note', 'note', 'source', 'assessment', 'source_bundle', 'run_revision', 'domain_actor'])
def test_release_cannot_skip_or_replace_its_evidence(mutation):
    _, _, _, pending, run, domain = path_to_release()
    body = command(pending, 'APPROVED_FOR_DEMO', run=run, domain_note=domain,
                   note=note(pending, 'RELEASE', 'APPROVE', APPROVER, 'a'*64))
    body['checks'] = checks(pending, gate_run_sha256=content_hash('evaluation-run', run),
                            source_bundle_id=pending['source_bundle_id'], source_eligible=True, assessment_sha256='a'*64)
    if mutation in ('run', 'domain_note', 'note'): body[mutation] = None
    if mutation == 'source': body['checks'] = replace(body['checks'], source_eligible=False)
    if mutation == 'assessment': body['checks'] = replace(body['checks'], assessment_sha256='b'*64)
    if mutation == 'source_bundle': body['checks'] = replace(body['checks'], source_bundle_id=run['adapter_version_id'])
    if mutation == 'run_revision': body['run']['recorded_revision'] = 1
    if mutation == 'domain_actor': body['domain_note']['actor_id'] = REQUESTER.actor_id
    with pytest.raises(DomainError):
        apply_transition(pending, body, APPROVER)


@pytest.mark.parametrize('mutation', ['missing', 'tenant', 'suite', 'revision', 'actor'])
def test_evaluation_run_binding(mutation):
    draft, _, _, _, run, _ = path_to_release()
    if mutation == 'tenant': run['tenant_id'] = 'tenant-b'
    if mutation == 'suite': run['suite_version_id'] = run['adapter_version_id']
    if mutation == 'revision': run['recorded_revision'] = 1
    if mutation == 'actor': run['actor_id'] = REVIEWER.actor_id
    body = command(draft, 'EVALUATION_RECORDED', run=None if mutation == 'missing' else run)
    with pytest.raises(DomainError):
        apply_transition(draft, body, REQUESTER)


def test_incomplete_record_is_saved_as_state_but_cannot_submit():
    draft, _, _, _, _, _ = path_to_release()
    run = load('run-incomplete')
    saved = apply_transition(draft, command(draft, 'EVALUATION_RECORDED', run=run), REQUESTER)
    assert saved['revision'] == 2 and saved['active_run_id'] == run['id']
    body = command(saved, 'SUBMITTED_FOR_DOMAIN_REVIEW', run=run)
    body['checks'] = checks(saved, gate_run_sha256=content_hash('evaluation-run', run))
    with pytest.raises(DomainError) as exc:
        apply_transition(saved, body, REQUESTER)
    assert exc.value.code == 'EVALUATION_INCOMPLETE'


@pytest.mark.parametrize('relation,state', [('CORRECTS_REJECTED','REJECTED'), ('REPLACES_DRAFT','DRAFT'), ('FOLLOWS_APPROVED','APPROVED_FOR_DEMO')])
def test_parent_relation_requires_matching_same_tenant_record(relation, state):
    parent = load('snapshot-genesis')
    parent['change_id'] = '00000000-0000-4000-8000-000000000099'
    parent['status'] = state
    if state == 'APPROVED_FOR_DEMO':
        parent.update(active_run_id=load('run-complete')['id'], domain_reviewer_id=REVIEWER.actor_id,
                      release_approver_id=APPROVER.actor_id, assessment_sha256='a'*64)
    body = command(None, 'CHANGE_CREATED', parent=parent)
    body['body'] = load('create-minimal')
    body['body'].update(parent_change_id=parent['change_id'], parent_relation=relation)
    saved = apply_transition(None, body, REQUESTER)
    assert saved['parent_change_id'] == parent['change_id']
    assert saved['active_run_id'] is None and saved['domain_reviewer_id'] is None and saved['assessment_sha256'] is None
    body['parent'] = None
    with pytest.raises(DomainError):
        apply_transition(None, body, REQUESTER)
    body['parent'] = dict(parent, tenant_id='tenant-b')
    with pytest.raises(DomainError) as exc:
        apply_transition(None, body, REQUESTER)
    assert exc.value.code == 'NOT_FOUND'


def test_revision_overflow_and_backward_clock_cannot_change_state():
    draft, _, _, _, run, _ = path_to_release()
    for value in (dict(draft, revision=9007199254740991), dict(draft, updated_at='2026-10-30T03:34:56.123456Z')):
        with pytest.raises(DomainError) as exc:
            apply_transition(value, command(value, 'EVALUATION_RECORDED', run=run), REQUESTER)
        assert exc.value.code == 'INVALID_REQUEST'
    body = command(None, 'EVALUATION_REQUESTED')
    with pytest.raises((DomainError, ValueError, TypeError)):
        apply_transition(None, body, REQUESTER)
