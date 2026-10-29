"""Malformed audit references must report invalid evidence instead of crashing."""
import json
import pytest
from sqlalchemy import select
from test_service import fx, auth, ready_for_release
from service.models import AuditEvent


@pytest.mark.parametrize('field,kind', [('evaluation_id','EVALUATION_RECORDED'),
                                       ('decision_id','DOMAIN_APPROVE')])
@pytest.mark.parametrize('value', [[], {}])
def test_unhashable_audit_reference_fails_closed(fx, field, kind, value):
    client, app = fx
    change = ready_for_release(client)
    with app.state.session_factory() as db:
        for event in db.scalars(select(AuditEvent)):
            payload = json.loads(event.event_json)
            if payload['kind'] == kind:
                payload['details'][field] = value
                event.event_json = json.dumps(payload)
                break
        db.commit()
    evidence = client.get(f"/api/changes/{change['id']}/evidence", headers=auth('aurora-auditor'))
    assert evidence.status_code == 200
    assert evidence.json()['record_integrity_verified'] is False
    result = client.post(f"/api/changes/{change['id']}/release-decision",
        headers=auth('aurora-approver'), json={'expected_revision':change['revision'],
        'decision':'APPROVE','reason':'Synthetic review of damaged evidence'})
    assert result.status_code == 409
