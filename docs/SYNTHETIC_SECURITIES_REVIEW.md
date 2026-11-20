# Synthetic securities document-review pack

`datasets/packs/synthetic_securities_review.json` is one invented internal
document-review specification for a fictional bond memo. It demonstrates reuse
of the existing scoped, bitemporal resolver through configuration. Its 10-day
and 7-day values are arbitrary fixture values, not a filing deadline, regulation,
market convention, investment recommendation, or trading instruction.

All source IDs, clauses and approval-history evidence labels are synthetic test
data. No human or regulator approved this pack. `APPROVED` is an input to the
resolver's synthetic state machine, not a certification.

## Explicit configuration boundary

The three existing insurance packs and default `/api/v1` workspace presets are
unchanged. This fourth pack is loaded explicitly with `PackRegistry`; it is not
a new default UI preset or a new HTTP onboarding path. The existing
`caseproof.policy-pack.v1` contract is preserved: values remain integer `days`.

For this example only, the legacy `consultation_date` context field means the
document-review effective date. It is not a publication date, reporting period,
settlement date, or a date inferred from a financial document. The required
date must be provided; `incident_date` cannot substitute for it. `CONFIRMED`
with an empty rider list explicitly confirms that this fixture has no rider
extensions. Supporting financial amounts, currencies or extracted periods would
need a separately designed schema and tests.

| Synthetic event | Rule selection |
| --- | --- |
| Review date before 2025-01-01 | INCONCLUSIVE |
| Review date 2025-01-01 through 2025-06-30, knowledge time from 2025-01-01 | 10 days from synthetic memo v1 |
| Review date from 2025-07-01, knowledge time from 2025-06-01 and before 2025-09-01 | 7 days from synthetic memo v2 |
| Knowledge time before v2 approval or at/after its 2025-09-01 revocation, for a July review | INCONCLUSIVE; no fallback to expired v1 |

These are two independent axes: a business date selects an effective rule;
`recorded_as_of` selects the source history known at that instant. Intervals are
half open. `RESOLVED` reports an applicable rule and provenance, not a PASS for
an entire document or a legal/investment conclusion.

## Reproduce locally

From the repository root, using the existing declared dependency environment:

```python
import json
from pathlib import Path
from service.policies import PackRegistry, resolve_context

registry = PackRegistry()
registry.register(json.loads(Path(
    'datasets/packs/synthetic_securities_review.json').read_text(encoding='utf-8')))
context = {
    'tenant_id': 'fictional', 'pack_id': 'securities-review-synthetic',
    'product_id': 'synthetic-bond-memo', 'workflow': 'document-review',
    'rule_key': 'internal-review-window', 'consultation_date': '2025-07-01',
    'rider_context_status': 'CONFIRMED', 'riders': [],
}
result = resolve_context(context,
    registry.get('fictional', 'securities-review-synthetic'),
    '2025-08-01T00:00:00Z')
assert (result['status'], result['value'], result['unit']) == ('RESOLVED', 7, 'days')
assert result['source_id'] == 'synthetic-memo-v2'
```

```bash
python -m pytest -q tests/policies
python -m pytest -q
python -m scripts.smoke
python -m scripts.check_ui_syntax
python -m scripts.check_package
python VERIFY_PACKAGE.py
```

Dedicated independent tests cover effective and recorded boundaries, draft and
revoked sources, scope isolation, missing dates, unknown context, conservative
priority/source rejection, defensive copies, version protection, and coexistence
with the original insurance fixtures. The unchanged full suite covers existing
approval separation, tenant authorization and actor-scoped idempotent retries.
Local execution evidence is recorded separately from remote CI; unavailable
PostgreSQL, numerical or browser suites must retain their explicit skip reasons.
