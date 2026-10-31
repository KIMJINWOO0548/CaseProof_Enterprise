"""Immutable full-suite synchronous execution for the numeric demo only."""
from service.api.errors import DomainError
from service.api.schemas_v1 import RecordEvaluation, EvaluationRunV2
from service.domain.canonical import content_hash
from service.domain.gates import check_run_gate, source_eligibility
from service.domain.state_machine import SNAPSHOT_IDS
from service.domain.types import json_payload
from service.evaluation.adapters import FakeDeterministicAdapter
from service.evaluation.config import execution_config_sha256


def prepare_run(history, body, actor, run_id, time, revision):
    try:
        request = RecordEvaluation.model_validate(json_payload(body)).model_dump(by_alias=True)
    except ValueError:
        raise DomainError('INVALID_REQUEST') from None
    snapshot, refs = history['snapshot'], history['refs']
    suite = refs['suite']
    if request['suite_version_id'] != snapshot['suite_version_id']:
        raise DomainError('SNAPSHOT_MISMATCH')
    required = suite['required_case_ids']
    if not required or len(required) != len(set(required)) or sorted(c['case_id'] for c in request['case_inputs']) != sorted(required):
        raise DomainError('INVALID_REQUEST')
    for key, name in zip(SNAPSHOT_IDS, ('candidate_snapshot','source_bundle','dataset','suite','evaluator')):
        if refs[name]['id'] != snapshot[key] or refs[name]['tenant_id'] != snapshot['tenant_id']:
            raise DomainError('SNAPSHOT_MISMATCH')
    adapters = [a for a in refs['adapters'] if a['id'] == refs['candidate_snapshot'].get('adapter_version_id')]
    if len(adapters) != 1 or adapters[0].get('kind') != 'fake-deterministic':
        raise DomainError('SNAPSHOT_MISMATCH')
    adapter = FakeDeterministicAdapter()
    results = []
    for case in sorted(request['case_inputs'], key=lambda c: c['case_id']):
        error = None
        try:
            output = adapter.execute(case)
            if (type(output) is not dict or set(output) != {'claim_days'} or
                    type(output['claim_days']) is not int or not 0 <= output['claim_days'] <= 9999):
                raise ValueError('invalid adapter output')
        except Exception as exc:
            error = 'ADAPTER_TIMEOUT' if isinstance(exc, TimeoutError) else 'ADAPTER_ERROR'
            output = {'error_code': error}
        allowed = suite.get('case_policy_versions', {}).get(case['case_id'], [])
        sources = [s for s in refs['sources'] if s['policy_version_id'] in allowed and s.get('status') == 'APPROVED']
        packs = [p['pack_snapshot'] for p in refs['policies'] if 'pack_snapshot' in p]
        if packs:
            from service.policies.resolver import resolve_context
            context = dict(case['case_context'], tenant_id=snapshot['tenant_id'], pack_id=snapshot['pack_version_id'],
                           product_id=snapshot['product_id'], workflow=snapshot['workflow'],rule_key=snapshot['rule_key'])
            resolution = resolve_context(context, packs[0], context['recorded_as_of']) if len(packs) == 1 else {'status':'INCONCLUSIVE','reason_codes':['POLICY_CONFLICT']}
            if resolution['status'] != 'RESOLVED':
                sources, error = [], resolution['reason_codes'][0]
            else:
                sources = [s for s in sources if s.get('source_id', s['id']) == resolution['source_id']
                           and s['policy_version_id'] == resolution['policy_version']]
                if any(s.get('value') != resolution['value'] for s in sources):
                    sources, error = [], 'SNAPSHOT_MISMATCH'
        values = {s.get('value', s.get('claim_days')) for s in sources}
        if len(values) != 1 or any(type(value) is not int or not 0 <= value <= 9999 for value in values):
            error = error or 'SOURCE_UNRESOLVED'
        complete = error is None
        results.append(dict(case_id=case['case_id'], input_sha256=content_hash('case-input',case),
            output_sha256=content_hash('case-output',output),
            source_refs=[{'id':s['id'],'payload_sha256':content_hash('source',s)} for s in sorted(sources,key=lambda s:s['id'])],
            resolution_status='RESOLVED' if complete else 'INCONCLUSIVE',
            verdict=('PASS' if output['claim_days'] == next(iter(values)) else 'FAIL') if complete else 'INCONCLUSIVE',
            complete=complete,error_code=error,critical_failure=False if complete else None))
    run = dict(schema='evaluation_run_v2',id=run_id,tenant_id=actor.tenant_id,change_id=snapshot['change_id'],
        recorded_revision=revision,actor_id=actor.actor_id,created_at=time,
        **{key:snapshot[key] for key in SNAPSHOT_IDS},adapter_version_id=adapters[0]['id'],
        run_input_sha256=content_hash('run-input',dict(request,case_inputs=sorted(request['case_inputs'],key=lambda c:c['case_id']))),
        run_config_sha256=execution_config_sha256(refs, adapters[0]),
        case_results=results)
    gate = check_run_gate(run,suite,source_eligibility(history))
    run.update(completion=gate['completion'],gate_summary=gate['gate_summary'])
    return EvaluationRunV2.model_validate(run).model_dump(by_alias=True)
