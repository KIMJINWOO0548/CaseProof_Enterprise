"""Smoke runs must preserve historical reports and support a chosen output."""
import json
from pathlib import Path
import pytest
from scripts.smoke import run


def test_smoke_writes_selected_new_report(tmp_path):
    output = tmp_path / 'run' / 'smoke.json'
    report = run(output=output)
    assert json.loads(output.read_text(encoding='utf-8')) == report
    assert report['result'] == 'PASS'
    assert len(report['checks']) == 12


def test_smoke_default_preserves_historical_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    historical = Path('reports/integration_smoke.json')
    historical.parent.mkdir()
    historical.write_text('historical evidence', encoding='utf-8')
    run()
    assert historical.read_text(encoding='utf-8') == 'historical evidence'
    assert len(list(Path('reports/runs').glob('*/integration_smoke.json'))) == 1


def test_smoke_refuses_existing_output(tmp_path):
    output = tmp_path / 'smoke.json'
    output.write_text('historical evidence', encoding='utf-8')
    with pytest.raises(FileExistsError):
        run(output=output)
    assert output.read_text(encoding='utf-8') == 'historical evidence'


@pytest.mark.parametrize('stage', ['tables', 'seed', 'client-start', 'request'])
def test_smoke_failure_disposes_database_and_never_publishes_report(tmp_path, monkeypatch, stage):
    from scripts import smoke
    calls = []
    create = smoke.create_app
    temporary = smoke.tempfile.TemporaryDirectory

    def tracked_app(*args, **kwargs):
        app = create(*args, **kwargs)
        dispose = app.state.db_engine.dispose

        def tracked_dispose():
            calls.append('disposed')
            dispose()

        monkeypatch.setattr(app.state.db_engine, 'dispose', tracked_dispose)
        return app

    def fail(*args, **kwargs):
        raise RuntimeError('injected smoke failure')

    class Client:
        def __init__(self, app):
            pass

        def __enter__(self):
            if stage == 'client-start':
                fail()
            return self

        def __exit__(self, *args):
            return False

        request = fail

    monkeypatch.setattr(smoke, 'create_app', tracked_app)
    monkeypatch.setattr(smoke.tempfile, 'TemporaryDirectory',
                        lambda **kwargs: temporary(dir=tmp_path, **kwargs))
    monkeypatch.setattr(smoke, 'TestClient', Client)
    if stage == 'tables':
        monkeypatch.setattr(smoke, 'create_tables', fail)
    elif stage == 'seed':
        monkeypatch.setattr(smoke, 'seed_demo', fail)
    output = tmp_path / 'report.json'
    with pytest.raises(RuntimeError, match='injected smoke failure'):
        smoke.run(output=output)
    assert calls == ['disposed']
    assert not output.exists()
    assert list(tmp_path.glob('caseproof_smoke_*')) == []
