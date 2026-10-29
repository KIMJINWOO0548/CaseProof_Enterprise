"""Submitting corrupt stored results must report an integrity error before parsing gates."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from service.models import Change, Evaluation
from test_service import auth, create, evaluate, fx


@pytest.mark.parametrize('corrupt_result', ['{invalid', 'null', '[]'])
def test_submit_rejects_malformed_result_without_state_change(fx, corrupt_result):
    client, app = fx
    change = create(client)
    assert evaluate(client, change).status_code == 201
    change['revision'] = 2
    assert evaluate(client, change, claim_days=20, basis_date='2026-07-01').status_code == 201
    with app.state.session_factory() as db:
        row = db.execute(select(Evaluation).where(Evaluation.change_id == change['id'])).scalars().first()
        row.result_json = corrupt_result
        db.commit()
    with TestClient(app, raise_server_exceptions=False) as guarded:
        result = guarded.post(f"/api/changes/{change['id']}/submit", headers=auth('aurora-analyst'),
                              json={'expected_revision': 3})
    assert result.status_code == 409, result.text
    assert result.json()['detail']['code'] == 'EVIDENCE_RECORD_TAMPERED'
    with app.state.session_factory() as db:
        record = db.get(Change, change['id'])
        assert (record.status, record.revision) == ('DRAFT', 3)
