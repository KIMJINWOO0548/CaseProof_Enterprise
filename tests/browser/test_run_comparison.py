"""Actual JS handlers; optional Node harness, separately from root browser QA."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_saved_run_comparison_handlers():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable; run-comparison handlers were not checked')
    result = subprocess.run([node, 'scripts/check_run_comparison.cjs'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
