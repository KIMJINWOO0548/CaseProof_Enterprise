import pytest
from service.evaluation.datasets import connected_groups, validate_split


def test_transitive_relations_stay_together():
    rows = [dict(case_id="a", document_family="d", split="dev"),
            dict(case_id="b", document_family="d", product_family="p", split="dev"),
            dict(case_id="c", product_family="p", incident_group="i", split="dev"),
            dict(case_id="d", incident_group="i", scenario_derivation="s", split="dev"),
            dict(case_id="e", scenario_derivation="s", split="dev"),
            dict(case_id="f", contract_group="c", split="validation")]
    assert connected_groups(rows) == {"a": "a", "b": "a", "c": "a", "d": "a", "e": "a", "f": "f"}
    validate_split(rows)
    rows[-2]["split"] = "blind"
    with pytest.raises(ValueError, match="crosses splits"):
        validate_split(rows)


def test_source_hash_and_public_private_id_alignment():
    rows = [dict(case_id="a", split="dev", source_hashes={"s": "1"}),
            dict(case_id="b", split="blind", source_hashes={"s": "2"})]
    with pytest.raises(ValueError, match="source hash"):
        validate_split(rows)
    with pytest.raises(ValueError, match="case IDs"):
        validate_split(rows[:1], private_case_ids={"other"})


def test_missing_relations_do_not_join_unrelated_cases():
    assert connected_groups([{"case_id": "b"}, {"case_id": "a"}]) == {"a": "a", "b": "b"}
    with pytest.raises(ValueError, match="duplicate"):
        connected_groups([{"case_id": "a"}, {"case_id": "a"}])


def test_shared_source_cannot_cross_splits():
    rows = [dict(case_id="a", split="dev", source_hashes={"s": "1"}),
            dict(case_id="b", split="blind", source_hashes={"s": "1"})]
    with pytest.raises(ValueError, match="crosses splits"):
        validate_split(rows)
