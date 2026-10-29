import json
from pathlib import Path

import pytest

from service.domain.canonical import canonical_bytes, content_hash, parse_json


VECTORS = Path(__file__).parents[1] / "fixtures" / "canonical_vectors_v1.json"


def test_all_canonical_vectors():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    for vector in vectors["vectors"]:
        payload = vector["input"]
        assert canonical_bytes(payload).hex() == vector["canonical_utf8_hex"], vector["id"]
        assert content_hash(vector["purpose"], payload) == vector["hash"], vector["id"]


def test_fixture_runtime_rejections():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    for vector in vectors["runtime_rejections"]:
        with pytest.raises((TypeError, ValueError)):
            parse_json(vector["raw_json"])


@pytest.mark.parametrize("raw", [b"\xef\xbb\xbf{}", b"\xff{}", b"{\"x\":\"\xed\xa0\x80\"}"])
def test_rejects_invalid_utf8_and_bom(raw):
    with pytest.raises((TypeError, ValueError, UnicodeError)):
        parse_json(raw)


@pytest.mark.parametrize("value", [1.0, 9007199254740992, {1: "x"}, {"x": "\ud800"}, (1,), {1, 2}])
def test_rejects_values_outside_canonical_domain(value):
    with pytest.raises((TypeError, ValueError)):
        canonical_bytes(value)


def test_hash_purpose_separates_identical_payloads_and_validates_syntax():
    assert content_hash("request", {}) != content_hash("assessment", {})
    for purpose in ("", "Request", "a:b", "é", "1request", "request\n"):
        with pytest.raises((TypeError, ValueError)):
            content_hash(purpose, {})


def test_parse_json_accepts_top_level_canonical_values():
    assert parse_json("null") is None
    assert parse_json("[]") == []
    assert parse_json("{}") == {}
    assert parse_json("\"한\"") == "한"

