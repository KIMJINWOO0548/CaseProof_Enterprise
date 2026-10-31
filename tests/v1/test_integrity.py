import pytest
from sqlalchemy import update
from service import models_v1 as m
from service.api.errors import DomainError
from service.commands import execute_command
from service.repositories import load_history
from tests.v1.helpers import setup, command, dump


@pytest.mark.parametrize('field,value', [('status', 'PENDING_RELEASE'), ('revision', 7), ('requester_id', 'reviewer'), ('owner_id', 'reviewer')])
def test_projection_tamper_rejected_without_side_effects(tmp_path, field, value):
    factory, actors, body = setup(tmp_path)
    created = execute_command(factory, actors['analyst'], command(body))
    identity = created.data['change_id']
    with factory.begin() as db:
        db.execute(update(m.Change).values(**{field: value}))
    before = dump(factory)
    with pytest.raises(DomainError) as error:
        execute_command(factory, actors['approver'], command({'decision': 'APPROVE', 'reason': 'Independent review'}, 'release-decision', identity, 1))
    assert error.value.status_code == 409
    assert dump(factory) == before


@pytest.mark.parametrize('field,value', [('sequence', 2), ('head_sha256', 'a' * 64)])
def test_tenant_head_tamper(tmp_path, field, value):
    factory, actors, body = setup(tmp_path)
    created = execute_command(factory, actors['analyst'], command(body))
    with factory.begin() as db:
        db.execute(update(m.TenantAuditHead).values(**{field: value}))
    with factory() as db, pytest.raises(DomainError, match='AUDIT_INTEGRITY_FAILURE'):
        load_history(db, 'tenant-a', created.data['change_id'])
