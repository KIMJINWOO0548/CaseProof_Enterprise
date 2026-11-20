"""Offline owner-reviewed restoration grants; no real identities or tokens."""
import hashlib
import pytest
from service import recovery
from service.auth import authenticate
from service.api.errors import DomainError
from service.db import make_engine, session_factory
from tests.v1.helpers import setup


def restored(tmp_path):
    factory, _, _ = setup(tmp_path)
    factory.kw['bind'].dispose()
    backup, target = tmp_path / 'backup.db', tmp_path / 'restored.db'
    metadata = recovery.backup_database(tmp_path / 'v1.db', backup)
    recovery.restore_database(backup, target, metadata)
    old = {hashlib.sha256(b'old-synthetic').hexdigest(): {'tenant_id':'tenant-a','actor_id':'analyst'}}
    new = {hashlib.sha256(b'new-synthetic').hexdigest(): {'tenant_id':'tenant-a','actor_id':'analyst'}}
    return target, old, new


def test_reviewed_allowlist_replaces_roles_and_preserves_other_revocations(tmp_path):
    target, old, new = restored(tmp_path)
    operation = getattr(recovery, 'reactivate_reviewed_actors', None)
    assert callable(operation), 'Missing safe owner-reviewed reactivation operation'
    report = operation(target, recovery.file_sha256(target), [{'tenant_id':'tenant-a','actor_id':'analyst','roles':['AUDITOR']}], old, new, 'synthetic-review-1')
    engine = make_engine('sqlite:///' + target.as_posix())
    try:
        with session_factory(engine)() as db:
            assert authenticate('new-synthetic', new, db).roles == frozenset(['AUDITOR'])
            with pytest.raises(DomainError):
                authenticate('old-synthetic', new, db)
            from service.models_v1 import Actor
            assert db.get(Actor, ('tenant-a','reviewer')).enabled is False
        assert report['review_reference'] == 'synthetic-review-1'
    finally:
        engine.dispose()


@pytest.mark.parametrize('failure', ['stale_digest','reused_token','unknown_actor','invalid_role','unreviewed_registry_actor'])
def test_reactivation_rejects_inconsistent_review_without_writes(tmp_path, failure):
    target, old, new = restored(tmp_path)
    operation = getattr(recovery, 'reactivate_reviewed_actors', None)
    assert callable(operation), 'Missing safe owner-reviewed reactivation operation'
    digest = recovery.file_sha256(target)
    grants = [{'tenant_id':'tenant-a','actor_id':'analyst','roles':['ANALYST']}]
    if failure == 'stale_digest': digest = '0' * 64
    if failure == 'reused_token': new = old
    if failure == 'unknown_actor': grants[0]['actor_id'] = 'missing'
    if failure == 'invalid_role': grants[0]['roles'] = ['ADMIN']
    if failure == 'unreviewed_registry_actor': new[next(iter(new))]['actor_id'] = 'reviewer'
    before = target.read_bytes()
    with pytest.raises(ValueError): operation(target, digest, grants, old, new, 'synthetic-review-1')
    assert target.read_bytes() == before

@pytest.mark.parametrize('failure', ['missing_review', 'duplicate_grant', 'already_active'])
def test_review_gate_does_not_allow_bulk_or_repeated_activation(tmp_path, failure):
    import sqlite3
    target, old, new = restored(tmp_path)
    grants = [{'tenant_id':'tenant-a','actor_id':'analyst','roles':['AUDITOR']}]
    if failure == 'duplicate_grant': grants.append(dict(grants[0]))
    if failure == 'already_active':
        with sqlite3.connect(target) as db:
            db.execute("UPDATE v1_actor SET enabled=1 WHERE id='reviewer'")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        recovery.reactivate_reviewed_actors(target, recovery.file_sha256(target), grants, old, new,
                                            '' if failure == 'missing_review' else 'review-1')
    assert target.read_bytes() == before
