"""Initializer and server must agree on the explicitly configured demo database."""
import os
import subprocess
import sys
from pathlib import Path


def test_cli_uses_environment_database_and_leaves_other_files_alone(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    target = tmp_path / 'chosen.sqlite3'
    default = tmp_path / 'caseproof_demo.sqlite3'
    default.write_bytes(b'do not touch')
    result = subprocess.run(
        [sys.executable, '-m', 'service.cli', 'init-demo'], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(repo), 'CASEPROOF_DEMO_MODE': '1',
             'CASEPROOF_DATABASE_URL': f'sqlite:///{target}'},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert target.is_file()
    assert default.read_bytes() == b'do not touch'
