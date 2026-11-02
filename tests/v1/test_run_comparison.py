"""Saved-run read boundaries and descriptive comparisons; disposable data only."""
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from service import models_v1 as m
from service.commands import execute_command
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.types import ActorContext, json_payload
from tests.v1.helpers import command, dump
from tests.v1.test_http import client_app, request
from tests.v1.test_runs import inputs
from tests.v1.test_workspace import workspace, headers, mutate


def saved_pair(tmp_path):
    app, factory, body = client_app(tmp_path)
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    identity = execute_command(factory, actor, command(body)).data['change_id']
    first = execute_command(factory, actor, command(inputs(body, 29), 'evaluation-runs', identity, 1)).data['run']
    second = execute_command(factory, actor, command(inputs(body), 'evaluation-runs', identity, 2)).data['run']
    return app, factory, identity, json_payload(first), json_payload(second)


def compare_url(identity, first, second):
    return (f'/api/v1/changes/{identity}/evaluation-runs/compare'
            f'?baseline_run_id={first["id"]}&candidate_run_id={second["id"]}')


def test_corrected_saved_runs_describe_context_and_never_write(tmp_path):
    app, factory, identity, first, second = saved_pair(tmp_path)
    before = dump(factory)
    listing = request(app, 'GET', f'/api/v1/changes/{identity}/evaluation-runs')
    assert listing.status_code == 200, listing.text
    data = listing.json()['data']
    assert data['schema'] == 'evaluation_run_history_v1'
    assert (data['total_runs'], data['limit'], data['truncated']) == (2, 100, False)
    assert [r['id'] for r in data['runs']] == [second['id'], first['id']]
    assert data['runs'][0]['payload_sha256'] == content_hash('evaluation-run', second)
    assert data['runs'][0]['run_config_sha256'] == second['run_config_sha256']
    response = request(app, 'GET', compare_url(identity, first, second))
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['schema'] == 'evaluation_comparison_v1'
    assert result['baseline']['id'] == first['id'] and result['candidate']['id'] == second['id']
    assert result['mode'] == 'CONTEXT_CHANGED'
    assert result['context_reasons'] == ['INPUT_CHANGED']
    assert result['changed_counts'] == dict(presence_changed=0, input_changed=2, output_changed=2,
                                          source_refs_changed=0, result_state_changed=2, any_changed=2)
    assert [r['case_id'] for r in result['rows']] == ['case-a', 'case-b']
    assert [(r['baseline']['verdict'], r['candidate']['verdict']) for r in result['rows']] == [('FAIL', 'PASS')] * 2
    assert all(r['changes']['input_changed'] for r in result['rows'])
    assert not {'claim_days', 'case_context', 'actor_id', 'tenant_id', 'gold'} & set(result['rows'][0]['baseline'])
    assert dump(factory) == before


def test_same_run_zero_change_and_caller_order(tmp_path):
    app, factory, identity, first, second = saved_pair(tmp_path)
    path = compare_url(identity, first, first)
    result = request(app, 'GET', path).json()['data']
    assert request(app, 'GET', path).json()['data'] == result
    assert result['mode'] == 'SAME_CONTEXT' and result['context_reasons'] == []
    assert set(result['changed_counts'].values()) == {0}
    reverse = request(app, 'GET', compare_url(identity, second, first)).json()['data']
    assert (reverse['baseline']['id'], reverse['candidate']['id']) == (second['id'], first['id'])
    assert reverse['rows'][0]['baseline']['verdict'] == 'PASS'


@pytest.mark.parametrize('query', ['', '?baseline_run_id=x&candidate_run_id=y', '?baseline_run_id={a}',
    '?baseline_run_id={a}&candidate_run_id={b}&extra=1',
    '?baseline_run_id={a}&baseline_run_id={a}&candidate_run_id={b}',
    '?baseline_run_id={a}&candidate_run_id={b}&candidate_run_id={b}',
    '?baseline_run_id=&candidate_run_id={b}',
    '?baseline_run_id=00000000-0000-1000-8000-000000000000&candidate_run_id={b}'])
def test_compare_query_is_exact_and_strict(tmp_path, query):
    app, factory, identity, first, second = saved_pair(tmp_path)
    before = dump(factory)
    response = request(app, 'GET', f'/api/v1/changes/{identity}/evaluation-runs/compare' + query.format(a=first['id'], b=second['id']))
    assert response.status_code == 422 and response.json()['error']['code'] == 'INVALID_REQUEST'
    assert dump(factory) == before


def test_history_rejects_query_and_auth_precedes_object_and_query_access(tmp_path):
    app, factory, identity, first, second = saved_pair(tmp_path)
    path = f'/api/v1/changes/{identity}/evaluation-runs'
    assert request(app, 'GET', path + '?limit=1').status_code == 422
    for suffix in ('', '/compare?extra=1'):
        response = request(app, 'GET', '/api/v1/changes/not-an-id/evaluation-runs' + suffix,
                           headers={'Authorization': 'Bearer missing'})
        assert response.status_code == 401
    with factory.begin() as db:
        db.get(m.Actor, ('tenant-a', 'analyst')).roles_payload = canonical_bytes([])
    for target in (path, compare_url(identity, first, second)):
        assert request(app, 'GET', target).status_code == 403
    with factory.begin() as db:
        db.get(m.Actor, ('tenant-a', 'analyst')).enabled = False
    assert request(app, 'GET', path).status_code == 401


def test_foreign_change_and_run_ids_are_generic_not_found(tmp_path):
    app, factory, identity, first, second = saved_pair(tmp_path)
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    body = request(app, 'GET', f'/api/v1/changes/{identity}').json()['data']['snapshot']
    create = {k: body[k] for k in ('title', 'pack_version_id', 'product_id', 'workflow', 'rule_key',
              'candidate_snapshot_id', 'source_bundle_id', 'dataset_version_id', 'suite_version_id', 'evaluator_version_id')}
    other = execute_command(factory, actor, command(create)).data['change_id']
    foreign = execute_command(factory, actor, command(inputs(create), 'evaluation-runs', other, 1)).data['run']
    for run in (foreign, dict(id=str(uuid4()))):
        response = request(app, 'GET', compare_url(identity, run, second))
        assert response.status_code == 404 and response.json()['error']['code'] == 'NOT_FOUND'
        assert response.json()['error']['details'] == {}
    assert request(app, 'GET', f'/api/v1/changes/{uuid4()}/evaluation-runs').status_code == 404


@pytest.mark.parametrize('kind', ['tampered', 'legacy'])
def test_unverified_history_fails_closed(tmp_path, monkeypatch, kind):
    if kind == 'legacy':
        import hashlib
        from fastapi import FastAPI
        from service.api.v1 import build_router
        from service.auth import DemoTokenAuthenticator
        from tests.v1.test_execution_config import legacy_evaluated
        factory, actors, identity, _, result = legacy_evaluated(tmp_path, monkeypatch)
        first = second = json_payload(result.data['run'])
        app = FastAPI()
        app.include_router(build_router(factory, DemoTokenAuthenticator({
            hashlib.sha256(b'analyst').hexdigest(): {'tenant_id': 'tenant-a', 'actor_id': 'analyst'}})))
    else:
        app, factory, identity, first, second = saved_pair(tmp_path)
        with factory.begin() as db:
            row = db.scalars(select(m.EvaluationRun).where(m.EvaluationRun.id == first['id'])).one()
            db.execute(text(f'DROP TRIGGER {m.EvaluationRun.__table__.name}_no_update'))
            row.canonical_payload = canonical_bytes(dict(first, created_at='2020-01-01T00:00:00.000000Z'))
    before = dump(factory)
    for path in (f'/api/v1/changes/{identity}/evaluation-runs', compare_url(identity, first, second)):
        response = request(app, 'GET', path)
        assert response.status_code == 409, response.text
        assert response.json()['error']['code'] == ('EXECUTION_CONFIG_UNVERIFIED' if kind == 'legacy' else 'EVIDENCE_RECORD_TAMPERED')
        assert 'data' not in response.json()
    assert dump(factory) == before


def test_cross_tenant_change_and_foreign_run_have_no_projection(workspace):
    client, factory, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    identity = change['change_id']
    run = mutate(client, f'/{identity}/evaluation-runs', dict(suite_version_id=change['suite_version_id'], case_inputs=preset['case_inputs']), 1)['run']
    before = dump(factory)
    for path in (f'/api/v1/changes/{identity}/evaluation-runs', compare_url(identity, run, run)):
        response = client.get(path, headers=headers('other'))
        assert response.status_code == 404 and response.json()['error']['code'] == 'NOT_FOUND'
        assert 'data' not in response.json()
    assert dump(factory) == before


def test_empty_history_then_one_run_same_comparison(tmp_path):
    app, factory, body = client_app(tmp_path)
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    identity = execute_command(factory, actor, command(body)).data['change_id']
    path = f'/api/v1/changes/{identity}/evaluation-runs'
    assert request(app, 'GET', path).json()['data'] == dict(schema='evaluation_run_history_v1',
        runs=[], total_runs=0, limit=100, truncated=False)
    run = execute_command(factory, actor, command(inputs(body), 'evaluation-runs', identity, 1)).data['run']
    response = request(app, 'GET', compare_url(identity, run, run))
    assert response.status_code == 200 and response.json()['data']['changed_counts']['any_changed'] == 0


def test_full_history_is_validated_before_limit_and_older_runs_remain_comparable(tmp_path):
    app, factory, body = client_app(tmp_path)
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    identity = execute_command(factory, actor, command(body)).data['change_id']
    runs = []
    for revision in range(1, 102):
        runs.append(execute_command(factory, actor, command(inputs(body), 'evaluation-runs', identity, revision)).data['run'])
    before = dump(factory)
    path = f'/api/v1/changes/{identity}/evaluation-runs'
    data = request(app, 'GET', path).json()['data']
    assert (len(data['runs']), data['total_runs'], data['truncated']) == (100, 101, True)
    assert runs[0]['id'] not in {run['id'] for run in data['runs']}
    assert request(app, 'GET', compare_url(identity, runs[0], runs[-1])).status_code == 200
    assert dump(factory) == before
    with factory.begin() as db:
        db.execute(text(f'DROP TRIGGER {m.EvaluationRun.__table__.name}_no_update'))
        row = db.get(m.EvaluationRun, ('tenant-a', runs[0]['id']))
        row.canonical_payload = canonical_bytes(dict(json_payload(runs[0]), gate_summary='BLOCK'))
    assert request(app, 'GET', path).status_code == 409
    assert request(app, 'GET', compare_url(identity, runs[-1], runs[-1])).status_code == 409


def test_api_case_limit_fails_safely_without_writes(tmp_path):
    from service.repositories import add_payload, decode
    app, factory, body = client_app(tmp_path)
    with factory.begin() as db:
        suite = decode(db.get(m.SuiteSnapshot, ('tenant-a', body['suite_version_id'])))
        suite.update(id=str(uuid4()), required_case_ids=[f'case-{i:04}' for i in range(1001)],
            case_policy_versions={f'case-{i:04}': [f'policy-v{i % 2 + 1}'] for i in range(1001)},
            coverage_by_case={f'case-{i:04}': [] for i in range(1001)})
        add_payload(db, m.SuiteSnapshot, suite)
    body['suite_version_id'] = suite['id']
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    identity = execute_command(factory, actor, command(body)).data['change_id']
    run = execute_command(factory, actor, command(dict(suite_version_id=suite['id'], case_inputs=[
        dict(case_id=name, claim_days=30, case_context={}) for name in suite['required_case_ids']]),
        'evaluation-runs', identity, 1)).data['run']
    before = dump(factory)
    response = request(app, 'GET', compare_url(identity, run, run))
    assert response.status_code == 422 and response.json()['error']['code'] == 'COMPARISON_LIMIT_EXCEEDED'
    assert response.json()['error']['details'] == {} and 'data' not in response.json()
    assert dump(factory) == before


def test_runtime_read_projections_match_versioned_contracts(tmp_path):
    from tests.v1.test_contracts import assert_schema
    from service.api.errors import DomainError, error_payload
    app, factory, identity, first, second = saved_pair(tmp_path)
    listing = request(app, 'GET', f'/api/v1/changes/{identity}/evaluation-runs').json()['data']
    comparison = request(app, 'GET', compare_url(identity, first, second)).json()['data']
    assert_schema(listing, 'evaluation-run-history-v1.schema.json')
    assert_schema(comparison, 'evaluation-comparison-v1.schema.json')
    assert_schema(error_payload(DomainError('COMPARISON_LIMIT_EXCEEDED'), str(uuid4())), 'error.schema.json')


def test_latest_incomplete_remains_authoritative_after_comparing_older_pass(tmp_path, monkeypatch):
    from service.api.errors import DomainError
    from service.evaluation.adapters import FakeDeterministicAdapter
    app, factory, identity, first, second = saved_pair(tmp_path)
    actor = ActorContext('tenant-a', 'analyst', frozenset(['ANALYST']))
    def timeout(self, case):
        raise TimeoutError('private adapter exception must not leak')
    monkeypatch.setattr(FakeDeterministicAdapter, 'execute', timeout)
    third = execute_command(factory, actor, command(inputs(second), 'evaluation-runs', identity, 3)).data['run']
    before = dump(factory)
    data = request(app, 'GET', compare_url(identity, second, third)).json()['data']
    assert data['mode'] == 'INCOMPLETE'
    assert all(row['baseline']['verdict'] == 'PASS' and row['candidate']['verdict'] == 'INCONCLUSIVE' for row in data['rows'])
    assert all(row['candidate']['error_code'] == 'ADAPTER_TIMEOUT' for row in data['rows'])
    assert 'private adapter exception' not in str(data)
    current = request(app, 'GET', f'/api/v1/changes/{identity}').json()['data']
    assert current['snapshot']['active_run_id'] == third['id']
    assert current['latest_run']['completion'] == 'INCOMPLETE'
    with pytest.raises(DomainError, match='EVALUATION_INCOMPLETE'):
        execute_command(factory, actor, command({}, 'submit', identity, 4))
    assert dump(factory) == before


def test_unauthenticated_history_and_comparison_never_return_data(tmp_path):
    app, factory, identity, first, second = saved_pair(tmp_path)
    before = dump(factory)
    for path in (f'/api/v1/changes/{identity}/evaluation-runs', compare_url(identity, first, second)):
        response = request(app, 'GET', path, headers={'X-Test': 'no-authorization'})
        assert response.status_code == 401 and 'data' not in response.json()
    assert dump(factory) == before
