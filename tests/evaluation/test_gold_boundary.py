"""Public synthetic boundary checks; these are not blind-study records."""
import pytest

from service.evaluation.datasets import (
    ModelCaseInput, assert_public_artifacts, model_payload, public_manifest,
)


def case_input():
    return dict(case_id="a", query="Synthetic deadline?", context_snapshot={"days": 3},
                source_bundle_id="public-v1", business_as_of="2026-10-28",
                recorded_as_of="2026-10-28T00:00:00.000000Z")


def test_model_allowlist_and_copy():
    source = case_input()
    result = model_payload(source)
    assert set(result) == set(ModelCaseInput.__dataclass_fields__)
    result["context_snapshot"]["days"] = 5
    assert source["context_snapshot"]["days"] == 3


@pytest.mark.parametrize("key", ["gold", "expected_reason", "severity", "risk_present",
                                "scenario_family", "gold_sha256", "private_path"])
def test_gold_and_metadata_are_not_model_inputs(key):
    value = case_input()
    value[key] = "secret"
    with pytest.raises(ValueError):
        model_payload(value)
    value = case_input()
    value["context_snapshot"]["nested"] = [{key: "secret"}]
    with pytest.raises(ValueError):
        model_payload(value)


@pytest.mark.parametrize("path", ["private/gold.json", "datasets/private_gold/a.json",
                                 "datasets/holdout-private/a.json", "x/gold.private.json"])
def test_private_files_cannot_be_public_artifacts(path):
    with pytest.raises(ValueError):
        assert_public_artifacts([path])


def test_ui_manifest_is_an_allowlist_without_case_gold_commitments():
    result = public_manifest({"dataset_version_id": "public-v1", "public_case_count": 2,
                              "gold_sha256": "private", "private_path": "private/x",
                              "case_results": [{"expected_reason": "private"}]})
    assert result == {"dataset_version_id": "public-v1", "public_case_count": 2}
