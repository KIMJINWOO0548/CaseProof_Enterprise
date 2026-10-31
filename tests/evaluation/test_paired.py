from copy import deepcopy
import builtins
import pytest

from service.evaluation.benchmark import compare_paired
from service.evaluation.datasets import GoldRecord
from service.evaluation.metrics import EvaluationDependencyUnavailable, paired_ci95


def fixture():
    gold = [GoldRecord("a", "CRITICAL", True), GoldRecord("b", "LOW", False)]
    metadata = [{"case_id": "a", "scenario_family": "same"},
                {"case_id": "b", "scenario_family": "same"}]
    row = lambda key: dict(case_id=key, input_sha256="1" * 64, source_sha256="2" * 64,
                           complete=True, correct=True, critical_failure=False, risk_flagged=False,
                           error_code=None)
    arm = dict(snapshots={key: "3" * 64 for key in
                         ("input_sha256", "source_sha256", "dataset_sha256", "gold_sha256",
                          "rubric_sha256", "evaluator_sha256")},
               policy={"budget_micro_usd": 100, "timeout_ms": 100, "retry": 0},
               settings={"model": "fake", "version": "1", "temperature": 0,
                         "seed": 1, "max_tokens": 10, "permissions": [],
                         "infrastructure": "local", "measurement_interval": "model"},
               case_results=[row("a"), row("b")])
    return arm, deepcopy(arm), gold, metadata


def compare(b, c, g, m, spec=None):
    return compare_paired(b, c, g, m, spec or {"allowed_differences": []})


def test_hand_count_severity_is_not_observed_failure():
    b, c, g, m = fixture()
    c["case_results"][0]["correct"] = False
    c["case_results"][0]["risk_flagged"] = True
    result = compare(b, c, g, m)
    assert result["status"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert result["accuracy"] == {"baseline": 1, "candidate": .5}
    assert result["accuracy_delta_pp"] == -50
    assert result["new_critical_ids"] == []
    assert result["risk_recall"] == {"baseline": 0, "candidate": 1}
    assert result["false_positive_rate"] == {"baseline": 0, "candidate": 0}
    assert result["paired_ci95"] is None
    assert result["ci_reason"] == "INSUFFICIENT_CLUSTERS"
    assert result["costs"]["candidate"]["model"]["value"] is None


def test_critical_regression_and_registered_gate_block():
    b, c, g, m = fixture()
    c["case_results"][0]["critical_failure"] = True
    result = compare(b, c, g, m)
    assert result["status"] == "BLOCKED"
    assert result["new_critical_ids"] == ["a"]
    c["case_results"][0]["critical_failure"] = False
    assert compare(b, c, g, m, {"allowed_differences": [], "minimum_accuracy": 1,
                              "maximum_new_critical": 0})["status"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    c["case_results"][0]["correct"] = False
    assert compare(b, c, g, m, {"allowed_differences": [], "minimum_accuracy": 1})["status"] == "BLOCKED"


def test_both_incomplete_keep_counts_and_raw_without_headlines():
    b, c, g, m = fixture()
    for arm in (b, c):
        arm["case_results"][0].update(complete=False, correct=None, critical_failure=None,
                                      risk_flagged=None, error_code="TIMEOUT")
    result = compare(b, c, g, m)
    assert result["status"] == "INCOMPLETE"
    assert result["counts"]["baseline"] == dict(attempted=2, completed=1, timeout=1, error=0)
    assert result["raw_results"]["candidate"] == c["case_results"]
    for key in ("accuracy", "accuracy_delta_pp", "paired_ci95", "risk_recall", "false_positive_rate"):
        assert result[key] is None


@pytest.mark.parametrize("mutation", ["case", "snapshot", "rubric", "policy", "severity", "duplicate", "group", "empty"])
def test_mismatched_contract_invalid(mutation):
    b, c, g, m = fixture()
    if mutation == "case": c["case_results"][0]["case_id"] = "unknown"
    if mutation in ("snapshot", "rubric"):
        c["snapshots"]["rubric_sha256" if mutation == "rubric" else "input_sha256"] = "4" * 64
    if mutation == "policy": c["policy"]["retry"] = 1
    if mutation == "severity": c["case_results"][0]["severity"] = "LOW"
    if mutation == "duplicate": c["case_results"].append(c["case_results"][0])
    if mutation == "group": m.pop()
    if mutation == "empty": b["case_results"] = []; c["case_results"] = []
    assert compare(b, c, g, m)["status"] == "INVALID"


def test_only_explicit_setting_difference_allowed_not_hash_override():
    b, c, g, m = fixture()
    c["settings"]["model"] = "candidate"
    assert compare(b, c, g, m)["status"] == "INVALID"
    assert compare(b, c, g, m, {"allowed_differences": ["model"]})["status"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    c["snapshots"]["gold_sha256"] = "5" * 64
    assert compare(b, c, g, m, {"allowed_differences": ["model", "gold_sha256"]})["status"] == "INVALID"


def test_zero_denominators_are_null_with_reason():
    b, c, _, m = fixture()
    for risk, key, reason in [(False, "risk_recall", "NO_POSITIVE_CASES"),
                               (True, "false_positive_rate", "NO_NEGATIVE_CASES")]:
        g = [GoldRecord("a", "LOW", risk), GoldRecord("b", "LOW", risk)]
        result = compare(b, c, g, m)
        assert result[key] == {"baseline": None, "candidate": None}
        assert result["metric_reasons"][key] == reason


def test_arm_group_override_is_invalid():
    b, c, g, m = fixture()
    c["case_results"][0]["scenario_family"] = "different"
    assert compare(b, c, g, m)["status"] == "INVALID"


def test_malformed_raw_results_fail_closed():
    b, c, g, m = fixture()
    c["case_results"] = [None]
    assert compare(b, c, g, m)["status"] == "INVALID"


def test_numpy_boundary_is_explicit(tmp_path, monkeypatch):
    original = builtins.__import__
    def absent(name, *args, **kwargs):
        if name == "numpy": raise ImportError("not installed")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", absent)
    with pytest.raises(EvaluationDependencyUnavailable, match="NumPy"):
        paired_ci95({"a": [1], "b": [-1]}, lock_path=tmp_path / "unused")


def test_exact_bootstrap_hand_checked_endpoints_and_reproducibility(tmp_path):
    np = pytest.importorskip("numpy", reason="numeric evaluation dependency not installed")
    lock = tmp_path / "requirements-evaluation.lock"
    lock.write_text(f"numpy=={np.__version__}\n", encoding="utf-8")
    first = paired_ci95({"z": [-1, -1, -1], "a": [1]}, lock_path=lock)
    assert first["interval"] == [-100, 100]
    assert first == paired_ci95({"a": [1], "z": [-1, -1, -1]}, lock_path=lock)
    assert first["numpy_version"] == np.__version__
    assert len(first["lock_sha256"]) == 64
    assert first["replicates"] == 10000
