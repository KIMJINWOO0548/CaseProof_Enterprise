"""Required development and safety guidance must ship with source packages."""
from pathlib import Path
import shutil

import pytest

from scripts.check_package import checks


@pytest.mark.parametrize("guide", ["prebuild/05_DEVELOPMENT_GUIDE.md", "AGENTS.md"])
def test_source_package_reports_missing_development_or_safety_guide(tmp_path, guide):
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "contracts", tmp_path / "contracts")
    (tmp_path / "tests/fixtures").mkdir(parents=True)
    shutil.copyfile(root / "tests/fixtures/canonical_vectors_v1.json",
                    tmp_path / "tests/fixtures/canonical_vectors_v1.json")
    problems, _ = checks(tmp_path)
    assert f"Missing required file: {guide}" in problems
