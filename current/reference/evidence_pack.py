"""Reproducible evidence hashing for synthetic demos.

SHA-256 can detect mutation against a trusted digest. It does NOT prove legal
non-repudiation, durable retention, or protection against an attacker rewriting
both records and their stored hashes. External anchoring is a production TODO.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def create_evidence_manifest(*, tenant_id: str, change_id: str, dataset_hash: str,
                             evaluator_hash: str, source_hashes: list[str],
                             findings_hash: str, recorded_at: str) -> dict:
    """All timestamps are caller-supplied and must be captured by trusted backend."""
    if not tenant_id or not change_id or not recorded_at:
        raise ValueError('missing required evidence identity')
    hashes = [dataset_hash, evaluator_hash, findings_hash, *source_hashes]
    if not all(isinstance(x, str) and len(x) == 64 and all(c in '0123456789abcdef' for c in x) for x in hashes):
        raise ValueError('hashes must be lowercase 64-char SHA-256 hex')
    content = {
        'schema': 'caseproof.evidence.v1', 'tenant_id': tenant_id,
        'change_id': change_id, 'dataset_sha256': dataset_hash,
        'evaluator_sha256': evaluator_hash, 'source_sha256': sorted(source_hashes),
        'findings_sha256': findings_hash, 'recorded_at': recorded_at,
    }
    return {'content': content, 'manifest_sha256': digest(content)}


def verify_manifest(manifest: dict, expected_tenant: str) -> bool:
    try:
        content = manifest['content']
        return (content['tenant_id'] == expected_tenant and
                manifest['manifest_sha256'] == digest(content))
    except (KeyError, TypeError, ValueError):
        return False


def append_audit_event(events: list[dict], event: dict) -> dict:
    """In-memory reference only. No DB concurrency protection."""
    prev = events[-1]['event_hash'] if events else '0' * 64
    item = {'prev_hash': prev, 'sequence': len(events) + 1, 'event': event}
    return {**item, 'event_hash': digest(item)}


def verify_audit_chain(events: list[dict]) -> bool:
    prev = '0' * 64
    for index, item in enumerate(events, 1):
        if item.get('prev_hash') != prev or item.get('sequence') != index:
            return False
        blob = {k: item[k] for k in ('prev_hash', 'sequence', 'event')}
        if item.get('event_hash') != digest(blob):
            return False
        prev = item['event_hash']
    return True
