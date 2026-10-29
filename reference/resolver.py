"""CaseProof synthetic reference PolicyResolver (NOT production insurance logic).

Requires stdlib only. Deterministic applicability; no legal determinations or AI.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
import json

RULES_FILE = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_rules.json"
DATE_FIELDS = {"contract_start_date", "incident_date", "claim_received_date", "question_date"}


@dataclass
class Resolution:
    status: str
    reason_codes: list[str]
    required_fields: list[str]
    rule_id: str | None = None
    policy_version: str | None = None
    value: int | None = None
    unit: str | None = None
    date_basis: str | None = None
    basis_date: str | None = None
    clause: str | None = None

    def as_json(self):
        return asdict(self)


def inconclusive(reason: str, required: list[str] | None = None):
    return Resolution("INCONCLUSIVE", [reason], required or [])


def _date(s: str) -> date:
    return date.fromisoformat(s)


def _datetime(s: str) -> datetime:
    value = datetime.fromisoformat(s)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of_recorded must have an explicit UTC offset")
    return value


def load_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))["rules"]


def resolve(query: dict, rules: list[dict] | None = None) -> Resolution:
    """Resolve synthetic policy version. Authenticated tenant identity is assumed external.

    This reference does not implement actual authentication; production backend MUST
    compare tenant to the authenticated actor, not trust caller's tenant string.
    """
    rules = rules if rules is not None else load_rules()
    for field in ("tenant", "product", "workflow", "rule_key"):
        if not query.get(field):
            return inconclusive("MISSING_" + field.upper(), [field])
    try:
        as_of = _datetime(query["as_of_recorded"])
    except (KeyError, TypeError, ValueError):
        return inconclusive("MISSING_OR_INVALID_RECORDED_TIME", ["as_of_recorded"])
    scope = [r for r in rules if all(r[k] == query[k] for k in ("tenant", "product", "workflow", "rule_key"))]
    if not scope:
        return inconclusive("NO_RULE_IN_SCOPE")
    # Intentionally block unsupported rider identifiers instead of silently ignoring them.
    codes = query.get("rider_codes", [])
    if not isinstance(codes, list) or not all(isinstance(x, str) for x in codes):
        return inconclusive("INVALID_RIDER_CONTEXT", ["rider_codes"])
    known = {r["rider"] for r in scope if r.get("rider")}
    if any(c not in known for c in codes):
        return inconclusive("MISSING_RIDER_CONTEXT", ["rider_codes"])
    # A selected rider cannot be silently discarded just because its source is
    # unapproved. This is a conservative synthetic rule, not an insurance-law policy.
    for r in scope:
        if r.get('rider') not in codes or r['source_state'] == 'PUBLISHED':
            continue
        try:
            basis = _date(query[r['date_basis']])
            applicable = (_date(r['valid_from']) <= basis < _date(r['valid_to'])
                          and _datetime(r['recorded_from']) <= as_of < _datetime(r['recorded_to']))
        except (KeyError, TypeError, ValueError):
            return inconclusive('INVALID_POLICY_OR_BASIS_DATE')
        if applicable:
            return inconclusive('SOURCE_NOT_APPROVED')
    active_scope = [r for r in scope if r["source_state"] == "PUBLISHED" and (r["rider"] is None or r["rider"] in codes)]
    if not active_scope:
        return inconclusive("SOURCE_NOT_APPROVED")
    bases = {r["date_basis"] for r in active_scope}
    if not bases.issubset(DATE_FIELDS):
        return inconclusive("UNSUPPORTED_DATE_BASIS")
    missing = [f for f in sorted(bases) if not query.get(f)]
    if missing:
        return inconclusive("MISSING_BASIS_DATE", missing)
    matches = []
    for r in active_scope:
        try:
            basis = _date(query[r["date_basis"]])
            recorded_start = _datetime(r["recorded_from"])
            recorded_end = _datetime(r["recorded_to"])
            valid = _date(r["valid_from"]) <= basis < _date(r["valid_to"])
        except (ValueError, TypeError, KeyError):
            return inconclusive("INVALID_POLICY_OR_BASIS_DATE")
        if valid and recorded_start <= as_of < recorded_end:
            matches.append(r)
    if not matches:
        return inconclusive("NO_APPLICABLE_RULE")
    top_priority = max(r["priority"] for r in matches)
    winners = [r for r in matches if r["priority"] == top_priority]
    if len(winners) != 1:
        return inconclusive("POLICY_CONFLICT")
    rule = winners[0]
    requested_version = query.get("requested_policy_version")
    if requested_version is not None and requested_version != rule["policy_version"]:
        return inconclusive("VERSION_INPUT_CONFLICT")
    return Resolution(
        "RESOLVED", ["POLICY_RESOLVED"], [],
        rule_id=rule["rule_id"], policy_version=rule["policy_version"],
        value=rule["value"], unit=rule["unit"],
        date_basis=rule["date_basis"], basis_date=query[rule["date_basis"]],
        clause=rule["clause"],
    )
