"""Pure, conservative source/time selection for validated synthetic snapshots."""
from service.api.schemas_v1 import CaseContext, RegisteredId, normalize_timestamp

from .schema import PolicyPack


class ResolutionContext(CaseContext):
    tenant_id: RegisteredId
    pack_id: RegisteredId
    product_id: RegisteredId
    workflow: RegisteredId
    rule_key: RegisteredId


def _within(value, start, end):
    return start <= value and (end is None or value < end)


def resolve_context(context: dict, pack_snapshot: dict, recorded_as_of: str) -> dict:
    """No clock/DB/network; authenticated tenant binding is the caller's responsibility."""
    result = dict(status='INCONCLUSIVE', reason_codes=[], required_fields=[], recorded_as_of=None,
                  candidates=[], rule_id=None, source_id=None, policy_version=None, clause_id=None,
                  value=None, unit=None, date_basis=None, basis_date=None, priority_version=None)

    def hold(code, required=()):
        result['reason_codes'] = [code]
        result['required_fields'] = sorted(required)
        return result

    try:
        pack = PolicyPack.model_validate(pack_snapshot)
    except (ValueError, TypeError):
        return hold('INVALID_PACK')
    try:
        asof = normalize_timestamp(recorded_as_of)
        result['recorded_as_of'] = asof
        facts = ResolutionContext.model_validate(context)
    except (ValueError, TypeError):
        return hold('INVALID_CONTEXT')
    if facts.recorded_as_of is not None and facts.recorded_as_of != asof:
        return hold('CONTRADICTING_CONTEXT')
    if (facts.tenant_id != pack.tenant_id or facts.pack_id != pack.pack_id
            or facts.product_id not in pack.product_ids):
        return hold('NO_RULE_IN_SCOPE')
    workflow = next((w for w in pack.workflows if w.workflow == facts.workflow), None)
    if workflow is None:
        return hold('NO_RULE_IN_SCOPE')
    rules = [r for r in pack.rules if (r.product_id, r.workflow, r.rule_key)
             == (facts.product_id, facts.workflow, facts.rule_key)]
    if not rules:
        return hold('NO_RULE_IN_SCOPE')
    sources = {s.source_id: s for s in pack.sources}
    statuses = {}
    for source in pack.sources:
        known = [e for e in source.approval_history if e.recorded_at <= asof]
        statuses[source.source_id] = known[-1].status if known else 'UNKNOWN'
    for rule in sorted(rules, key=lambda r: r.rule_id):
        reasons = []
        if not _within(asof, rule.recorded_from, rule.recorded_to):
            reasons.append('OUTSIDE_RECORDED_INTERVAL')
        if statuses[rule.source_id] != 'APPROVED':
            reasons.append('SOURCE_NOT_APPROVED')
        result['candidates'].append(dict(rule_id=rule.rule_id, source_id=rule.source_id,
            policy_version=sources[rule.source_id].policy_version, clause_id=rule.clause_id,
            eligible=False, reason_codes=reasons))
    missing = [field for field in workflow.required_dates if getattr(facts, field) is None]
    if missing:
        return hold('MISSING_REQUIRED_DATE', missing)
    basis = getattr(facts, workflow.date_basis)
    result.update(date_basis=workflow.date_basis, basis_date=basis, priority_version=pack.priorities.version)
    if facts.rider_context_status != 'CONFIRMED':
        return hold('UNKNOWN_RIDER_CONTEXT', ['rider_context_status'])
    if len({r.code for r in facts.riders}) != len(facts.riders):
        return hold('CONTRADICTING_CONTEXT')
    if any(r.enrolled_from is None or r.confirmation_evidence_id is None for r in facts.riders):
        return hold('MISSING_RIDER_CONTEXT')
    known_codes = {r.rider_code for r in rules if r.rider_code is not None}
    if any(r.code not in known_codes for r in facts.riders):
        return hold('UNKNOWN_RIDER')
    active_riders = {r.code for r in facts.riders if _within(basis, r.enrolled_from, r.enrolled_to)}
    candidates = {c['rule_id']: c for c in result['candidates']}
    eligible = []
    blocked_riders = set()
    for rule in rules:
        candidate = candidates[rule.rule_id]
        reasons = candidate['reason_codes']
        if not _within(basis, rule.valid_from, rule.valid_to):
            reasons.append('OUTSIDE_BUSINESS_INTERVAL')
        if rule.rider_code is not None and rule.rider_code not in active_riders:
            reasons.append('RIDER_NOT_APPLICABLE')
        if (rule.rider_code in active_riders and _within(asof, rule.recorded_from, rule.recorded_to)
                and _within(basis, rule.valid_from, rule.valid_to)
                and statuses[rule.source_id] != 'APPROVED'):
            blocked_riders.add(rule.rider_code)
        if not reasons:
            candidate['eligible'] = True
            eligible.append(rule)
    if blocked_riders:
        return hold('SOURCE_NOT_APPROVED')
    # An enrolled rider without an applicable approved rule has unknown impact.
    if active_riders - {r.rider_code for r in eligible}:
        return hold('RIDER_POLICY_UNRESOLVED')
    if not eligible:
        return hold('NO_APPLICABLE_APPROVED_RULE')
    retro = next(p for p in pack.retroactivity_policies if p.policy_id == pack.retroactivity_policy_id)
    if not pack.priorities.approved or (any(r.retroactive for r in eligible) and not retro.reviewed):
        return hold('POLICY_CONFLICT')
    highest = max(pack.priorities.ranks[r.priority_key] for r in eligible)
    winners = [r for r in eligible if pack.priorities.ranks[r.priority_key] == highest]
    if len(winners) != 1:
        return hold('POLICY_CONFLICT')
    selected = winners[0]
    for rule in eligible:
        if rule.rule_id != selected.rule_id:
            candidates[rule.rule_id]['eligible'] = False
            candidates[rule.rule_id]['reason_codes'].append('LOWER_PRIORITY')
    result.update(status='RESOLVED', reason_codes=['APPROVED_RULE_SELECTED'],
                  rule_id=selected.rule_id, source_id=selected.source_id,
                  policy_version=sources[selected.source_id].policy_version,
                  clause_id=selected.clause_id, value=selected.value, unit=selected.unit)
    return result
