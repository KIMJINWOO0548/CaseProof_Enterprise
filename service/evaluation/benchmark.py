"""Paired comparisons isolated from the legacy public-demo benchmark."""
from copy import deepcopy
import math
import re

from .datasets import GoldRecord, connected_groups
from .metrics import paired_ci95

_HASHES = {"input_sha256", "source_sha256", "dataset_sha256", "gold_sha256",
           "rubric_sha256", "evaluator_sha256"}
_SETTINGS = {"model", "version", "temperature", "seed", "max_tokens", "permissions",
             "infrastructure", "measurement_interval"}
_JUDGMENTS = ("correct", "critical_failure", "risk_flagged")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _index(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("case set must be nonempty")
    result = {}
    for row in rows:
        key = row.get("case_id")
        if type(key) is not str or not key or key in result:
            raise ValueError("missing or duplicate case ID")
        result[key] = row
    return result


def _counts(rows):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return dict(attempted=0, completed=0, timeout=0, error=0)
    return dict(attempted=len(rows), completed=sum(row.get("complete") is True for row in rows),
                timeout=sum(row.get("error_code") == "TIMEOUT" for row in rows),
                error=sum(row.get("error_code") not in (None, "TIMEOUT") for row in rows))


def _measurements(arm, section, channels):
    values = arm.get(section, {})
    result = {}
    for channel in channels:
        value = values.get(channel)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("cost/latency must be nonnegative integer micro-USD/milliseconds")
        result[channel] = {"value": value, "reason": "NOT_RECORDED" if value is None else None}
    return result


def compare_paired(baseline: dict, candidate: dict, gold: list[GoldRecord],
                   metadata: list[dict], comparison_spec: dict, *, lock_path=None) -> dict:
    """Return invalid/incomplete evidence before attempting any headline statistics.

    Only settings named in the preregistered allowed_differences may differ.
    Immutable input/source/dataset/gold/rubric/evaluator and execution policy
    remain identical; model/prompt changes belong in the settings manifest.
    """
    arms = {"baseline": baseline, "candidate": candidate}
    raw = {name: deepcopy(arm.get("case_results", [])) for name, arm in arms.items()}
    result = dict(status="INVALID", reasons=[], accuracy=None, accuracy_delta_pp=None,
                  paired_ci95=None, ci_reason=None, risk_recall=None, false_positive_rate=None,
                  metric_reasons={}, new_critical_ids=None,
                  counts={name: _counts(rows) for name, rows in raw.items()}, raw_results=raw,
                  provenance={name: deepcopy({key: arm.get(key) for key in ("snapshots", "policy", "settings")})
                              for name, arm in arms.items()})
    try:
        allowed = comparison_spec["allowed_differences"]
        if not isinstance(allowed, list) or len(set(allowed)) != len(allowed) or not set(allowed) <= _SETTINGS | {"prompt_sha256"}:
            raise ValueError("allowed_differences must name explicit settings only")
        if set(comparison_spec) - {"allowed_differences", "minimum_accuracy", "maximum_new_critical"}:
            raise ValueError("unknown preregistered gate")
        minimum = comparison_spec.get("minimum_accuracy")
        if minimum is not None and (type(minimum) not in (int, float) or not math.isfinite(minimum) or not 0 <= minimum <= 1):
            raise ValueError("minimum_accuracy must be between zero and one")
        max_critical = comparison_spec.get("maximum_new_critical", 0)
        if type(max_critical) is not int or max_critical < 0:
            raise ValueError("maximum_new_critical must be nonnegative integer")
        indexed = {name: _index(rows) for name, rows in raw.items()}
        ids = set(indexed["baseline"])
        if ids != set(indexed["candidate"]):
            raise ValueError("case IDs differ")
        gold_index = {}
        for record in gold:
            if not isinstance(record, GoldRecord) or record.case_id in gold_index:
                raise ValueError("gold must contain unique evaluator-owned GoldRecords")
            gold_index[record.case_id] = record
        meta = _index(metadata)
        if ids != set(gold_index) or ids != set(meta):
            raise ValueError("case/gold/group IDs differ")
        connected_groups(metadata)
        if any(type(row.get("scenario_family")) is not str or not row["scenario_family"] for row in metadata):
            raise ValueError("scenario_family is required")
        for name, arm in arms.items():
            snapshots = arm["snapshots"]
            if set(snapshots) != _HASHES or any(type(value) is not str or not _HEX.fullmatch(value) for value in snapshots.values()):
                raise ValueError("immutable snapshot hashes are required")
            policy = arm["policy"]
            if set(policy) != {"budget_micro_usd", "timeout_ms", "retry"} or any(type(value) is not int or value < 0 for value in policy.values()):
                raise ValueError("budget/timeout/retry policy is required")
            if not _SETTINGS <= set(arm["settings"]):
                raise ValueError("model and execution settings must be recorded")
            for row in indexed[name].values():
                if "severity" in row or "risk_present" in row:
                    raise ValueError("severity/risk belong exclusively to GoldRecord")
                if "scenario_family" in row and row["scenario_family"] != meta[row["case_id"]]["scenario_family"]:
                    raise ValueError("case group mismatch")
                if type(row.get("complete")) is not bool:
                    raise ValueError("complete must be boolean")
                if any((type(row.get(key)) is not bool if row["complete"] else row.get(key) is not None) for key in _JUDGMENTS):
                    raise ValueError("judgments must be boolean for complete cases and null otherwise")
                for key in ("input_sha256", "source_sha256"):
                    if type(row.get(key)) is not str or not _HEX.fullmatch(row[key]):
                        raise ValueError("case input/source hash is required")
                if row.get("error_code") is not None and (type(row["error_code"]) is not str or not row["error_code"]):
                    raise ValueError("invalid error code")
                if row["complete"] and row.get("error_code") is not None:
                    raise ValueError("complete case cannot carry execution error")
            result.setdefault("costs", {})[name] = _measurements(arm, "cost_micro_usd", ("model", "infrastructure", "human_review"))
            result.setdefault("latency", {})[name] = _measurements(arm, "latency_ms", ("model", "total", "human_review"))
        if baseline["snapshots"] != candidate["snapshots"] or baseline["policy"] != candidate["policy"]:
            raise ValueError("snapshot or budget/timeout/retry mismatch")
        settings_keys = set(baseline["settings"]) | set(candidate["settings"])
        if any(key not in allowed and baseline["settings"].get(key) != candidate["settings"].get(key) for key in settings_keys):
            raise ValueError("unregistered settings difference")
        for key in ids:
            if any(indexed["baseline"][key][field] != indexed["candidate"][key][field] for field in ("input_sha256", "source_sha256")):
                raise ValueError("paired case input/source mismatch")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        result["reasons"] = [str(exc)]
        return result
    if any(not row["complete"] for rows in indexed.values() for row in rows.values()):
        result.update(status="INCOMPLETE", reasons=["one or both arms contain incomplete cases"])
        return result
    n = len(ids)
    result["accuracy"] = {name: sum(row["correct"] for row in rows.values()) / n for name, rows in indexed.items()}
    result["accuracy_delta_pp"] = 100 * sum(int(indexed["candidate"][key]["correct"]) - int(indexed["baseline"][key]["correct"]) for key in ids) / n
    for headline, positive, reason in (("risk_recall", True, "NO_POSITIVE_CASES"),
                                       ("false_positive_rate", False, "NO_NEGATIVE_CASES")):
        selected = [key for key in ids if gold_index[key].risk_present is positive]
        result[headline] = {name: (sum(rows[key]["risk_flagged"] for key in selected) / len(selected) if selected else None) for name, rows in indexed.items()}
        if not selected:
            result["metric_reasons"][headline] = reason
    new_critical = sorted(key for key in ids if indexed["candidate"][key]["critical_failure"] and not indexed["baseline"][key]["critical_failure"])
    result["new_critical_ids"] = new_critical
    groups = {}
    for key in sorted(ids):
        groups.setdefault(meta[key]["scenario_family"], []).append(int(indexed["candidate"][key]["correct"]) - int(indexed["baseline"][key]["correct"]))
    bootstrap = paired_ci95(groups, lock_path=lock_path)
    result.update(paired_ci95=bootstrap["interval"], ci_reason=bootstrap["reason"], bootstrap=bootstrap,
                  cluster_count=len(groups), critical_case_count=sum(record.severity == "CRITICAL" for record in gold),
                  source_count=len({row["source_sha256"] for row in indexed["baseline"].values()}))
    blocked = bool(new_critical) or len(new_critical) > max_critical or (minimum is not None and result["accuracy"]["candidate"] < minimum)
    result["status"] = "BLOCKED" if blocked else "ELIGIBLE_FOR_HUMAN_REVIEW"
    return result
