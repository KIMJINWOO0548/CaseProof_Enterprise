import pytest
from service.commands import execute_command
from service.repositories import load_history
from tests.v1.helpers import setup, command, dump


def test_genesis_reconstructs(tmp_path):
    factory, actors, body = setup(tmp_path)
    result = execute_command(factory, actors['analyst'], command(body))
    assert result.status_code == 201 and result.result_revision == 1
    with factory() as db:
        history = load_history(db, 'tenant-a', result.data['change_id'])
    assert history['snapshot']['status'] == 'DRAFT'
    assert len(history['snapshots']) == len(history['transitions']) == len(history['events']) == 1


@pytest.mark.parametrize('stage', ['projection', 'note', 'snapshot', 'transition', 'audit', 'head', 'idempotency'])
def test_every_stage_rolls_back_every_table(tmp_path, monkeypatch, stage):
    factory, actors, body = setup(tmp_path)
    before = dump(factory)
    def fail(actual):
        if actual == stage:
            raise RuntimeError('injected failure')
    monkeypatch.setattr('service.commands.checkpoint', fail)
    with pytest.raises(RuntimeError):
        execute_command(factory, actors['analyst'], command(body))
    assert dump(factory) == before


def test_evaluation_submit_domain_approval(tmp_path):
    from tests.v1.helpers import pending_release
    factory, actors, body = setup(tmp_path)
    identity = pending_release(factory, actors, body)
    with factory() as db:
        history = load_history(db, 'tenant-a', identity)
    assert history['snapshot']['status'] == 'PENDING_RELEASE'
    assert len(history['transitions']) == 4 and len(history['runs']) == 1 and len(history['decisions']) == 1


@pytest.mark.parametrize('stage', ['projection', 'note', 'snapshot', 'transition', 'audit', 'head', 'idempotency'])
@pytest.mark.parametrize('cancelled', [False, True])
def test_release_failure_restores_every_record(tmp_path, monkeypatch, stage, cancelled):
    from asyncio import CancelledError
    from tests.v1.helpers import pending_release
    factory, actors, body = setup(tmp_path)
    identity = pending_release(factory, actors, body)
    before = dump(factory)
    failure = CancelledError if cancelled else RuntimeError
    def interrupt(actual):
        if actual == stage:
            raise failure('injected before commit')
    monkeypatch.setattr('service.commands.checkpoint', interrupt)
    with pytest.raises(failure):
        execute_command(factory, actors['approver'], command(
            {'decision': 'APPROVE', 'reason': 'Independent synthetic review'}, 'release-decision', identity, 4))
    assert dump(factory) == before
