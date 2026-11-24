"""Node DOM handler check; does not claim browser layout or human review."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_current_source_eligibility_label():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is unavailable; evidence label handler check was not run')
    # Windows hosted runners can take more than 15 seconds to start the Node process.
    result = subprocess.run([node, 'scripts/check_evidence_labels.cjs'],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, timeout=45 if os.name == 'nt' else 15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS: source eligibility stays distinct' in result.stdout
