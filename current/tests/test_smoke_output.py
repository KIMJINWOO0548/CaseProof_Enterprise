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
