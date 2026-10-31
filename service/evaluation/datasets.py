"""Evaluator-only gold and explicit public/model projections (contract §13)."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from service.domain.canonical import canonical_bytes


@dataclass(frozen=True)
class ModelCaseInput:
    case_id: str
    query: str
    context_snapshot: dict
    source_bundle_id: str
    business_as_of: str
    recorded_as_of: str


@dataclass(frozen=True)
class GoldRecord:
    """Evaluator-owned judgments; never serialize into an adapter payload."""
    case_id: str
    severity: str
    risk_present: bool
    ground_truth_status: str | None = None
    expected_claim_or_constraint: str | None = None
    expected_reason: str | None = None
    allowed_citation_spans: tuple = ()
    rubric_version: str | None = None
    annotator_ids: tuple = ()
    adjudicator_id: str | None = None

    def __post_init__(self):
        if not self.case_id or self.severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("invalid gold identity/severity")
        if type(self.risk_present) is not bool:
            raise ValueError("risk_present must be boolean")


_METADATA = {"scenario_family", "document_family", "product_family", "contract_group",
             "incident_group", "scenario_derivation", "split", "pack_id", "product_id",
             "private_path", "gold_sha256", "gold_freeze_hash", "dataset_version"}
_FORBIDDEN = (set(GoldRecord.__dataclass_fields__) - {"case_id"}) | _METADATA


def _reject_annotations(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _FORBIDDEN or key.lower().startswith(("gold", "expected_", "private_")):
                raise ValueError("gold/metadata is forbidden in model input")
            _reject_annotations(item)
    elif isinstance(value, list):
        for item in value:
            _reject_annotations(item)


def model_payload(value: ModelCaseInput | dict) -> dict:
    """Reject extra fields rather than quietly hiding a leaky caller."""
    data = asdict(value) if isinstance(value, ModelCaseInput) else deepcopy(value)
    if not isinstance(data, dict) or set(data) != set(ModelCaseInput.__dataclass_fields__):
        raise ValueError("model input must contain exactly the allowlisted fields")
    if any(type(data[key]) is not str or not data[key].strip()
           for key in data if key != "context_snapshot"):
        raise ValueError("model input strings must be nonempty")
    if type(data["context_snapshot"]) is not dict:
        raise ValueError("context_snapshot must be an object")
    canonical_bytes(data)
    _reject_annotations(data)
    return data


def assert_public_artifacts(paths) -> None:
    """Check ZIP/Git/source inventories; confidentiality still needs access control."""
    for path in paths:
        parts = PurePosixPath(str(path).replace("\\", "/")).parts
        if any(p.lower() in {"private", "holdout-private", "private_gold"}
               or p.lower().startswith("gold.private.") for p in parts):
            raise ValueError("private gold cannot enter public artifacts")


def public_manifest(manifest: dict) -> dict:
    return deepcopy({key: manifest[key] for key in ("dataset_version_id", "public_case_count")
                     if key in manifest})


_RELATIONS = ("document_family", "product_family", "contract_group", "incident_group",
              "scenario_derivation", "scenario_family", "source_version_ids", "document_original_ids")


def connected_groups(metadata: list[dict]) -> dict[str, str]:
    ids = [row["case_id"] for row in metadata]
    if any(type(key) is not str or not key for key in ids) or len(set(ids)) != len(ids):
        raise ValueError("empty or duplicate case IDs")
    parents = {key: key for key in ids}

    def find(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    seen = {}
    for row in metadata:
        for relation in _RELATIONS:
            values = list(row.get("source_hashes", {})) if relation == "source_version_ids" and not row.get(relation) else row.get(relation)
            if values is None or values == "":
                continue
            values = values if isinstance(values, list) else [values]
            for value in values:
                if type(value) is not str or not value:
                    raise ValueError("group relation must be a nonempty string")
                token = (relation, value)
                if token in seen:
                    left, right = find(row["case_id"]), find(seen[token])
                    parents[max(left, right)] = min(left, right)
                seen[token] = row["case_id"]
    return {key: find(key) for key in sorted(ids)}


def validate_split(metadata: list[dict], *, private_case_ids=None) -> dict[str, str]:
    groups = connected_groups(metadata)
    if private_case_ids is not None and set(groups) != set(private_case_ids):
        raise ValueError("public/private manifest case IDs differ")
    splits, source_hashes = {}, {}
    for row in metadata:
        split = row.get("split")
        if split not in {"dev", "validation", "blind"}:
            raise ValueError("unknown or missing split")
        for source, digest in row.get("source_hashes", {}).items():
            if source in source_hashes and source_hashes[source] != digest:
                raise ValueError("source hash mismatch")
            source_hashes[source] = digest
        group = groups[row["case_id"]]
        if group in splits and splits[group] != split:
            raise ValueError("connected group crosses splits")
        splits[group] = split
    return groups
