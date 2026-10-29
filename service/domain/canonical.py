"""Isolated caseproof.c14n.v1 serialization; legacy evidence hashes are unchanged."""
import hashlib
import json
import re
from typing import Any

_SAFE_INTEGER = 9_007_199_254_740_991
_PURPOSE = re.compile(r"[a-z][a-z0-9-]*\Z", re.ASCII)


def _validate(value: Any) -> None:
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is int:
        if not -_SAFE_INTEGER <= value <= _SAFE_INTEGER:
            raise ValueError("integer outside safe range")
        return
    if kind is str:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("surrogate code point is forbidden")
        return
    if kind is list:
        for item in value:
            _validate(item)
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("object keys must be strings")
            _validate(key)
            _validate(item)
        return
    raise TypeError(f"unsupported canonical value: {kind.__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Serialize an allowed protocol value as compact, sorted UTF-8 JSON."""
    try:
        _validate(value)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except RecursionError as exc:
        raise ValueError("canonical value is too deeply nested") from exc


def content_hash(purpose: str, value: Any) -> str:
    """Return the v1 SHA-256 digest for a protocol purpose and value."""
    if type(purpose) is not str or not _PURPOSE.fullmatch(purpose):
        raise ValueError("purpose must match [a-z][a-z0-9-]*")
    prefix = f"caseproof:{purpose}:v1\n".encode("ascii")
    return hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is forbidden: {value}")


def _reject_float(_value: str) -> None:
    raise ValueError("JSON floats are forbidden")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes | str) -> Any:
    """Parse strict UTF-8 JSON and reject values outside the v1 domain."""
    if type(raw) is bytes:
        source = raw.decode("utf-8", errors="strict")
    elif type(raw) is str:
        source = raw
    else:
        raise TypeError("JSON input must be bytes or str")
    if source.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is forbidden")
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
        _validate(value)
        return value
    except RecursionError as exc:
        raise ValueError("JSON input is too deeply nested") from exc
