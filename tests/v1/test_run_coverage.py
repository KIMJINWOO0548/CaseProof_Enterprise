from sqlalchemy import text
from service import models_v1 as m
from service.domain.canonical import canonical_bytes
from tests.v1.test_workspace import workspace, headers, mutate
from tests.v1.test_run_comparison import saved_pair
from tests.v1.test_http import request
from tests.v1.test_contracts import assert_schema


def test_saved_coverage(tmp_path):
    app, factory, change, first, second = saved_pair(tmp_path)
    url = f"/api/v1/changes/{change}/evaluation-runs/{first['id']}/coverage"
    response = request(app, "GET", url)
    assert response.status_code == 200
    data = response.json()["data"]
    assert_schema(data, 'evaluation-coverage-v1.schema.json')
    assert data["run_id"] == first["id"]
    assert [c["case_id"] for c in data["cases"]] == ["case-a", "case-b"]
    assert data["run_input_sha256"] == first["run_input_sha256"]

def test_coverage_from_migrated_workspace(workspace):
    client, factory, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    cases = preset['case_inputs']
    cases[0]['claim_days'] += 1
    run = mutate(client, '/' + change['change_id'] + '/evaluation-runs',
                 {'suite_version_id': change['suite_version_id'], 'case_inputs': cases}, 1)['run']
    url = f"/api/v1/changes/{change['change_id']}/evaluation-runs/{run['id']}/coverage"
    report = client.get(url, headers=headers()).json()['data']
    assert_schema(report, 'evaluation-coverage-v1.schema.json')
    assert report['clause_count'] == report['executed_clause_count'] == 1
    assert report['clauses'][0]['failed'] == 1
    assert report['cases'][0]['selected_rule_id'] == 'harbor-base'
    assert client.get(url, headers=headers('other')).status_code == 404
    with factory.begin() as db:
        db.get(m.Actor, ('fictional', 'analyst')).roles_payload = canonical_bytes([])
    assert client.get(url, headers=headers()).status_code == 403


def test_absent_and_corrupt_report(tmp_path):
    app, factory, change, first, second = saved_pair(tmp_path)
    url = f"/api/v1/changes/{change}/evaluation-runs/{first['id']}/coverage"
    with factory.begin() as db:
        db.execute(text('DROP TRIGGER v1_evaluation_coverage_no_update'))
        db.execute(text("UPDATE v1_evaluation_coverage SET canonical_payload=X'FF'"))
    assert request(app, 'GET', url).json()['error']['code'] == 'EVIDENCE_RECORD_TAMPERED'
    with factory.begin() as db:
        db.execute(text('DROP TRIGGER v1_evaluation_coverage_no_delete'))
        db.execute(text('DELETE FROM v1_evaluation_coverage'))
    assert request(app, 'GET', url).json()['data'] == dict(version=1, run_id=first['id'],
        availability='UNAVAILABLE', reason='NO_SAVED_COVERAGE')

def test_coverage_rollback_and_idempotent_retry(tmp_path, monkeypatch):
    import pytest
    from service import commands
    from tests.v1.helpers import command, dump, setup
    from tests.v1.test_runs import inputs
    factory, actors, body = setup(tmp_path)
    actor = actors['analyst']
    change = commands.execute_command(factory, actor, command(body)).data['change_id']
    record = command(inputs(body), 'evaluation-runs', change, 1)
    before = dump(factory)

    def fail(stage):
        if stage == 'snapshot':
            raise RuntimeError('synthetic failure after coverage insert')

    with monkeypatch.context() as patch:
        patch.setattr(commands, 'checkpoint', fail)
        with pytest.raises(RuntimeError, match='synthetic'):
            commands.execute_command(factory, actor, record)
    assert dump(factory) == before
    commands.execute_command(factory, actor, record)
    commands.execute_command(factory, actor, record)
    after = dump(factory)
    assert len(after['v1_evaluation_run']) == len(after['v1_evaluation_coverage']) == 1


def test_only_highest_eligible_rules_are_ties():
    import json
    from pathlib import Path
    from service.policies.resolver import resolve_context
    pack = json.loads(Path('datasets/packs/fictional_harbor.json').read_text())
    base = pack['rules'][0]
    pack['rules'] += [dict(base, rule_id='higher-b', priority_key='rider'),
                      dict(base, rule_id='higher-a', priority_key='rider')]
    facts = dict(tenant_id=pack['tenant_id'], pack_id=pack['pack_id'], product_id=base['product_id'],
                 workflow=base['workflow'], rule_key=base['rule_key'], contract_date='2025-02-01',
                 incident_date='2025-02-02', rider_context_status='CONFIRMED', riders=[])
    for approved, expected in [(True, ['higher-a','higher-b']), (False, [])]:
        pack['priorities']['approved'] = approved
        ties = []
        result = resolve_context(facts, pack, '2025-03-01T00:00:00Z', tie_rule_ids=ties)
        assert result['reason_codes'] == ['POLICY_CONFLICT']
        assert ties == expected

def test_half_open_boundaries_and_fixed_order():
    import json
    from pathlib import Path
    from service.domain.state_machine import SNAPSHOT_IDS
    from service.evaluation.coverage import build_coverage
    from service.policies.resolver import resolve_context
    pack = json.loads(Path('datasets/packs/fictional_harbor.json').read_text())
    rule = pack['rules'][0]
    rule['valid_to'] = '2025-03-01'
    scope = {key: rule[key] for key in ('product_id', 'workflow', 'rule_key')}
    history = dict(refs={'policies':[{'pack_snapshot':pack}]}, snapshot=dict(scope,
                   tenant_id=pack['tenant_id'], pack_version_id=pack['pack_id']))
    run = dict(id='fixed', recorded_revision=2, run_input_sha256='0'*64, **{k:k for k in SNAPSHOT_IDS})
    cases = []
    for day in ('2025-02-28', '2025-03-01'):
        facts = dict(scope, tenant_id=pack['tenant_id'], pack_id=pack['pack_id'], contract_date=day,
                     incident_date=day, rider_context_status='CONFIRMED', riders=[])
        result = resolve_context(facts, pack, '2025-03-02T00:00:00Z')
        resolved = result['status'] == 'RESOLVED'
        cases.append(dict(case_id=day, basis_date=day, selected_rule_id=result['rule_id'], complete=resolved,
                     reason_codes=result['reason_codes'], verdict='FAIL' if resolved else 'INCONCLUSIVE',
                     candidates=result['candidates']))
    report = build_coverage(history, run, cases)
    assert canonical_bytes(report) == canonical_bytes(build_coverage(history, run, cases[::-1]))
    assert report['gap_case_ids'] == ['2025-03-01']
    row = report['clauses'][0]
    assert row['case_ids'] == ['2025-02-28'] and row['failed'] == 1
    end = [b['case_ids'] for b in row['boundaries'] if b['boundary'] == 'valid_to']
    assert end == [['2025-02-28'], ['2025-03-01']]
