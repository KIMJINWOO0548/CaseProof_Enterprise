"""Actual JS-handler checks; no browser, screenshot or accessibility claim."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_submission_guidance_and_safe_conflict_recovery():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is unavailable; submit-flow handler check was not run')
    result = subprocess.run([node, 'scripts/check_submit_flow.cjs'],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS: submit flow (15 scenarios)' in result.stdout
