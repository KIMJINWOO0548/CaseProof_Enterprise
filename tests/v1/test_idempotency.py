import pytest
from sqlalchemy import update
from service import models_v1 as m
from service.api.errors import DomainError
from service.commands import execute_command
from service.domain.canonical import canonical_bytes
from tests.v1.helpers import setup, command, dump


def test_replay_preserves_original_status_and_data(tmp_path):
    factory, actors, body = setup(tmp_path)
    request = command(body)
    first = execute_command(factory, actors['analyst'], request)
    before = dump(factory)
    second = execute_command(factory, actors['analyst'], request)
    assert second.status_code == first.status_code == 201
    assert second.data == first.data and second.result_revision == 1 and second.replayed
    assert dump(factory) == before


def test_replay_precedes_latest_integrity(tmp_path):
    factory, actors, body = setup(tmp_path)
    request = command(body)
    first = execute_command(factory, actors['analyst'], request)
    with factory.begin() as db:
        db.execute(update(m.Change).values(status='PENDING_RELEASE'))
        db.execute(update(m.TenantAuditHead).values(head_sha256='e' * 64))
    assert execute_command(factory, actors['analyst'], request).data == first.data


@pytest.mark.parametrize('enabled,roles,code', [(False, ['ANALYST'], 'UNAUTHENTICATED'), (True, [], 'FORBIDDEN')])
def test_revoked_actor_cannot_replay(tmp_path, enabled, roles, code):
    factory, actors, body = setup(tmp_path)
    request = command(body)
    execute_command(factory, actors['analyst'], request)
    with factory.begin() as db:
        db.execute(update(m.Actor).where(m.Actor.id == 'analyst').values(enabled=enabled, roles_payload=canonical_bytes(roles)))
    with pytest.raises(DomainError, match=code):
        execute_command(factory, actors['analyst'], request)


def test_changed_body_conflicts_and_failure_does_not_reserve_key(tmp_path):
    factory, actors, body = setup(tmp_path)
    request = command(body)
    execute_command(factory, actors['analyst'], request)
    with pytest.raises(DomainError, match='IDEMPOTENCY_CONFLICT'):
        execute_command(factory, actors['analyst'], command(dict(body, title='changed'), key=request.key))
    before = dump(factory)
    with pytest.raises(DomainError, match='FORBIDDEN'):
        execute_command(factory, actors['reviewer'], command(body, key='reusable_key_123'))
    assert dump(factory) == before
    execute_command(factory, actors['analyst'], command(body, key='reusable_key_123'))
