"""Read-only report computed from the same resolver calls as the saved run."""
from datetime import date, timedelta

from sqlalchemy import select

from service import models_v1 as m
from service.domain.canonical import canonical_bytes, content_hash, parse_json
from service.domain.state_machine import SNAPSHOT_IDS
from service.repositories import require


def build_coverage(history, run, cases):
    packs = [p['pack_snapshot'] for p in history['refs']['policies'] if 'pack_snapshot' in p]
    snapshot = history['snapshot']
    pack = packs[0] if len(packs) == 1 else None
    if any(c['reason_codes'] == ['INVALID_PACK'] for c in cases):
        pack = None
    if pack and (pack['tenant_id'] != snapshot['tenant_id'] or pack['pack_id'] != snapshot['pack_version_id']):
        pack = None
    rows = []
    cases = sorted(cases, key=lambda c: c['case_id'])
    if pack:
        versions = {s['source_id']: s['policy_version'] for s in pack['sources']}
        for rule in sorted(pack['rules'], key=lambda r: (r['clause_id'], r['rule_id'])):
            if any(rule[k] != snapshot[k] for k in ('product_id', 'workflow', 'rule_key')):
                continue
            selected = [c for c in cases if c['selected_rule_id'] == rule['rule_id'] and c['complete']]
            boundaries = []
            for key in ('valid_from', 'valid_to'):
                if not rule.get(key):
                    continue
                day = date.fromisoformat(rule[key])
                for offset in (-1, 0):
                    if offset == -1 and day == date.min:
                        continue
                    target = (day + timedelta(days=offset)).isoformat()
                    matching = [c['case_id'] for c in cases if c['basis_date'] == target
                        and (c['selected_rule_id'] or c['reason_codes'] == ['NO_APPLICABLE_APPROVED_RULE'])
                        and any(x['rule_id'] == rule['rule_id'] and set(x['reason_codes']) <=
                                {'OUTSIDE_BUSINESS_INTERVAL', 'LOWER_PRIORITY'} for x in c['candidates'])]
                    boundaries.append(dict(boundary=key, offset=offset, date=target, case_ids=matching))
            rows.append(dict(rule_id=rule['rule_id'], clause_id=rule['clause_id'], policy_version=versions[rule['source_id']],
                case_ids=[c['case_id'] for c in selected],
                unselected_candidate_count=sum(c['selected_rule_id'] != rule['rule_id'] and
                    any(x['rule_id'] == rule['rule_id'] for x in c['candidates']) for c in cases),
                passed=sum(c['verdict']=='PASS' for c in selected),
                failed=sum(c['verdict']=='FAIL' for c in selected), boundaries=boundaries))
    return dict(version=1, availability='AVAILABLE', run_id=run['id'], recorded_revision=run['recorded_revision'],
        run_input_sha256=run['run_input_sha256'], **{k: run[k] for k in SNAPSHOT_IDS},
        clause_count=len({r['clause_id'] for r in rows}) if pack is not None else None,
        case_count=len(cases), executed_case_count=sum(bool(c['selected_rule_id']) and c['complete'] for c in cases),
        executed_clause_count=len({r['clause_id'] for r in rows if r['case_ids']}),
        inconclusive_case_count=sum(not c['complete'] or not c['selected_rule_id'] for c in cases),
        gap_case_ids=[c['case_id'] for c in cases if c['reason_codes'] == ['NO_APPLICABLE_APPROVED_RULE']],
        clauses=rows, cases=cases)


def read_coverage(db, run):
    rows = db.scalars(select(m.EvaluationCoverage).where(m.EvaluationCoverage.tenant_id == run['tenant_id'],
        m.EvaluationCoverage.run_id == run['id'], m.EvaluationCoverage.format_version == 1).limit(2)).all()
    require(len(rows) <= 1, 'EVIDENCE_RECORD_TAMPERED')
    if not rows:
        return dict(version=1, availability='UNAVAILABLE', run_id=run['id'], reason='NO_SAVED_COVERAGE')
    row = rows[0]
    try:
        report = parse_json(row.canonical_payload)
        valid = (canonical_bytes(report) == row.canonical_payload and report['version'] == 1
                 and report['run_id'] == row.run_id and report['run_input_sha256'] == row.run_input_sha256 == run['run_input_sha256']
                 and row.payload_sha256 == content_hash('evaluation-coverage', report)
                 and row.evaluation_sha256 == content_hash('evaluation-run', run))
    except (KeyError, ValueError, TypeError):
        valid = False
    require(valid, 'EVIDENCE_RECORD_TAMPERED')
    return report
