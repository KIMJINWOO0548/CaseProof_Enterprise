# G3 fictional policy packs

`service.policies.resolve_context(context, pack_snapshot, recorded_as_of)` is a
pure resolver for a **synthetic business specification**, separate from
`reference/resolver.py`. It makes no real insurance or legal determination.
All three `datasets/packs/fictional_*.json` files are invented paper-product
examples. Their APPROVED/review evidence labels are fictional test inputs,
not records of human review or real approvals.

## Consumption

```python
import json
from pathlib import Path
from service.policies import PackRegistry, resolve_context

registry = PackRegistry()
pack = json.loads(Path('datasets/packs/fictional_lantern.json').read_text(encoding='utf-8'))
registry.register(pack)  # The third pack needs no resolver changes.
context = {
    'tenant_id': 'fictional', 'pack_id': 'lantern', 'product_id': 'paper',
    'workflow': 'review', 'rule_key': 'window',
    'contract_date': '2025-01-01', 'incident_date': '2025-04-01',
    'rider_context_status': 'CONFIRMED', 'riders': [],
}
result = resolve_context(context, registry.get('fictional', 'lantern'),
                         '2025-08-01T09:00:00+09:00')
assert (result['status'], result['value']) == ('RESOLVED', 24)
```

The flat context extends the existing strict `CaseContext` with required
`tenant_id, pack_id, product_id, workflow, rule_key`. Callers bind tenant scope
from the authenticated actor; this pure function does not authenticate users.
Unknown fields/types fail closed. Omitted dates become null and rider context
defaults to UNKNOWN. An optional context `recorded_as_of` must equal the explicit
argument after UTC normalization. Rider confirmation IDs follow the existing
UUIDv4 DTO. CONFIRMED with an empty riders array means confirmed absence.

The result has `status` RESOLVED/INCONCLUSIVE, `reason_codes`, `required_fields`,
canonical UTC `recorded_as_of`, sorted `candidates`, nullable `rule_id`,
`source_id`, `policy_version`, `clause_id`, `value`, `unit`, `date_basis`,
`basis_date`, and `priority_version`. Every scoped candidate identifies its
source/version/clause and records `eligible` and exclusion `reason_codes`.
`POLICY_CONFLICT` is a reason on an INCONCLUSIVE result, never a positive result.
Resolution is applicability selection, not a PASS verdict for a numeric claim.

## Deliberate conservative decisions

1. Tenant/pack/product/workflow/rule-key scope is selected first. Source
   history and recorded intervals are evaluated at the explicit as-of instant.
   Required business dates and the workflow's versioned single date basis
   follow, then enrolled rider scope and approved versioned priorities.
2. All intervals are half open. Null ends mean infinity. Registration rejects
   from >= to, invalid dates/times, unknown references, duplicate IDs, and
   unordered or duplicate source-history instants. UTC normalization accepts
   explicit offsets and preserves microsecond precision.
3. Business date fields remain strict YYYY-MM-DD under the existing DTO. They
   already denote a date in the declared business timezone; the resolver does
   not turn them into midnight UTC or infer a date from another event. IANA
   timezone names require the host timezone database; unknown/unavailable zones
   fail registration. UTC works without optional timezone packages. The three
   supplied examples use UTC and were tested on Windows without tzdata.
4. Missing dates, UNKNOWN rider context, duplicate rider facts, absent rider
   confirmation, unknown rider codes, and active riders without applicable
   approved rules hold resolution. An applicable DRAFT/REVOKED rider blocks
   fallback even when an approved base candidate exists. A rider enrollment
   interval ending at the basis date is inactive.
5. All equal top-priority candidates hold resolution, including duplicates
   with the same numeric value: distinct provenance is not automatically
   interchangeable. Any eligible rule declaring retroactivity requires its
   registered policy to be reviewed. Retroactivity is explicit pack data;
   no insurance-law inference is made from entry dates. Unapproved priority
   policy also holds resolution.
6. Registry copies inputs/outputs, retains registered pack versions, rejects
   altered approval-history prefixes, and requires new identifiers for changed
   priority/date-basis/retroactivity definitions. Registry is configuration
   storage in memory; the application owns immutable DB snapshots and durable
   registration authorization. Source version IDs are stable RegisteredIds.

## Verification boundary

Independent tests in `tests/policies/` cover temporal boundaries, distinct date
bases, UTC offsets, strict registration, historical revocation, rider holds,
scope isolation, configuration-only three-pack registration, and append-only
version constraints. RED and target GREEN command logs are under
`reports/runs/*-g3-*`. Whole-suite/API/DB/browser integration is a separate
coordinator check. No external tester, production data, network model,
independent human approval, or real insurance validation is claimed.
