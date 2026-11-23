from uuid import uuid4

import pytest
from sqlalchemy import select, update

from service import models_v1 as m
from service.domain.canonical import canonical_bytes
from service.repositories import add_payload, decode
from tests.v1.helpers import dump
from tests.v1.test_evidence_http import create, fixture, post
from tests.v1.test_http import request


@pytest.fixture
def review_app(tmp_path):
    app, factory, body = fixture(tmp_path)
    try:
        yield app, factory, body
    finally:
        factory.kw['bind'].dispose()


def review(app, identity, actor='analyst'):
    response = request(app, 'GET', f'/api/v1/changes/{identity}/review',
                       headers={'Authorization': f'Bearer {actor}'})
    assert response.status_code == 200, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    return response.json()['data']


def evaluate(app, body, path, claim_days):
    return post(app, path + '/evaluation-runs', {'suite_version_id': body['suite_version_id'],
                'case_inputs': [{'case_id': case, 'claim_days': claim_days, 'case_context': {}}
                                for case in ('case-a', 'case-b')]}, revision=1)['run']


def revoke_source(factory):
    with factory.begin() as db:
        eligibility = decode(db.execute(select(m.SourceEligibilitySnapshot)).scalar_one())
        add_payload(db, m.SourceEligibilitySnapshot, dict(eligibility, id=str(uuid4()), sequence=2, eligible=False))


def test_readiness_keeps_case_gate_separate_from_source(review_app):
    app, factory, body = review_app
    identity = create(app, body, 'created')
    path = f'/api/v1/changes/{identity}'

    initial = review(app, identity)
    assert (initial['change_id'], initial['revision'], initial['status']) == (identity, 1, 'DRAFT')
    assert initial['evaluation'] is None
    assert initial['actions']['evaluate'] == {'allowed': True, 'reason': None}
    assert initial['actions']['submit'] == {'allowed': False, 'reason': 'EVALUATION_INCOMPLETE'}

    run = evaluate(app, body, path, claim_days=29)
    before = dump(factory)
    blocked = review(app, identity)
    assert dump(factory) == before
    assert blocked['current_approval_eligibility'] == 'ELIGIBLE'
    assert blocked['evaluation']['run_id'] == run['id']
    assert blocked['evaluation']['current_gate_summary'] == 'BLOCK'
    assert 'CASE_NOT_PASS' in blocked['evaluation']['gate_reasons']
    assert blocked['actions']['submit'] == {'allowed': False, 'reason': 'RELEASE_GATE_BLOCKED'}
    assert blocked['actions']['domain_approve'] == {'allowed': False, 'reason': 'FORBIDDEN'}


def test_current_roles_and_source_block_approval_but_not_independent_rejection(review_app):
    app, factory, body = review_app
    identity = create(app, body, 'evaluated')
    path = f'/api/v1/changes/{identity}'
    post(app, path + '/submit', {}, revision=2)
    assert review(app, identity, 'reviewer')['actions']['domain_approve']['allowed']
    post(app, path + '/domain-decision', {'decision': 'APPROVE', 'reason': 'Independent domain review'}, 'reviewer', 3)
    with factory.begin() as db:
        actor = db.get(m.Actor, ('tenant-a', 'reviewer'))
        actor.roles_payload = canonical_bytes(['DOMAIN_REVIEWER', 'RELEASE_APPROVER'])
    assert review(app, identity, 'reviewer')['actions']['release_approve'] == {
        'allowed': False, 'reason': 'SEPARATION_OF_DUTIES'}

    assert review(app, identity, 'approver')['actions']['release_approve']['allowed']
    revoke_source(factory)
    blocked = review(app, identity, 'approver')
    assert blocked['evaluation']['gate_summary'] == 'PASS'
    assert blocked['current_approval_eligibility'] == 'BLOCKED'
    assert blocked['actions']['release_approve'] == {'allowed': False, 'reason': 'RELEASE_GATE_BLOCKED'}
    assert blocked['actions']['release_reject'] == {'allowed': True, 'reason': None}
    post(app, path + '/release-decision', {'decision': 'REJECT', 'reason': 'Eligibility was withdrawn'}, 'approver', 4)


def test_seal_keeps_frozen_sources_and_decisions_while_current_source_changes(review_app):
    app, factory, body = review_app
    identity = create(app, body, 'approved')
    initial = review(app, identity)
    assert initial['historical_integrity'] == 'VALID'
    assert initial['current_approval_eligibility'] == 'ELIGIBLE'
    seal = initial['seal']
    assert (seal['preapproval_revision'], seal['approved_revision']) == (4, 5)
    assert seal['run_id'] == initial['evaluation']['run_id']
    assert seal['run_config_sha256'] == initial['evaluation']['run_config_sha256']
    assert seal['decision_id'] == initial['decisions'][1]['id']
    assert initial['decisions'][1]['reason'] == 'Independent release review'
    assert all(source['status'] == 'APPROVED' for source in seal['sources'])
    assert len(seal['sources']) == 2
    assert not any('claim_days' in source for source in seal['sources'])

    revoke_source(factory)
    withdrawn = review(app, identity)
    assert withdrawn['current_approval_eligibility'] == 'BLOCKED'
    assert withdrawn['envelope_sha256'] == initial['envelope_sha256']
    assert withdrawn['seal'] == seal
    assert withdrawn['decisions'] == initial['decisions']


def test_review_is_tenant_authorized_and_withholds_invalid_history(review_app):
    app, factory, body = review_app
    identity = create(app, body, 'approved')
    path = f'/api/v1/changes/{identity}/review'
    for actor, status in [('missing', 401), ('no-role', 403), ('outsider', 404)]:
        denied = request(app, 'GET', path, headers={'Authorization': f'Bearer {actor}'})
        assert denied.status_code == status
        assert 'Independent release review' not in denied.text
    assert request(app, 'GET', path + '?revision=5').status_code == 422

    with factory.begin() as db:
        db.execute(update(m.Change).where(m.Change.id == identity).values(status='REJECTED'))
    invalid = review(app, identity)
    assert invalid['historical_integrity'] == 'INVALID'
    assert invalid['seal'] is None and invalid['evaluation'] is None
    assert invalid['decisions'] == []
    assert not any(action['allowed'] for action in invalid['actions'].values())
