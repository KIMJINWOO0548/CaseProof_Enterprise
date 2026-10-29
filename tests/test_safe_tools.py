"""Tools must isolate temporary state and never overwrite an existing report."""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_importing_browser_tool_has_no_database_or_network_side_effects(tmp_path):
    sentinel = tmp_path / '_temporary_ui_demo.sqlite3'
    sentinel.write_text('keep this unrelated database', encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-c', 'import scripts.browser_e2e'],
        cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert sentinel.read_text(encoding='utf-8') == 'keep this unrelated database'


def test_smoke_refuses_to_overwrite_existing_report(tmp_path):
    from scripts.smoke import run
    target = tmp_path / 'existing.json'
    target.write_text('preserved', encoding='utf-8')
    with pytest.raises(FileExistsError):
        run(output=target)
    assert target.read_text(encoding='utf-8') == 'preserved'


def test_smoke_writes_requested_report_without_fixed_paths(tmp_path, monkeypatch):
    from scripts.smoke import run
    monkeypatch.chdir(tmp_path)
    target = tmp_path / 'new' / 'run.json'
    report = run(output=target)
    assert report['result'] == 'PASS'
    assert len(report['checks']) == 12
    assert target.is_file()
    assert not (tmp_path / 'reports' / 'integration_smoke.json').exists()
