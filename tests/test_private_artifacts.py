from pathlib import Path
import subprocess
import shutil

import pytest

from VERIFY_PACKAGE import source_files
from scripts.check_distribution import check_paths
from scripts.check_package import checks


@pytest.mark.parametrize('name', ['private/cases.json', 'datasets/private_gold/answers.json',
                                 'nested/holdout-private/data.json', 'datasets/gold.private.json'])
def test_private_paths_excluded_from_source_and_distributions(tmp_path, name):
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text('{}')
    (tmp_path / 'public.json').write_text('{}')
    assert [p.relative_to(tmp_path).as_posix() for p in source_files(tmp_path)] == ['public.json']
    with pytest.raises(SystemExit, match='private'):
        check_paths({name})


def test_force_tracked_private_gold_is_rejected(tmp_path):
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / 'contracts', tmp_path / 'contracts')
    (tmp_path / 'tests' / 'fixtures').mkdir(parents=True)
    shutil.copyfile(root / 'tests/fixtures/canonical_vectors_v1.json',
                    tmp_path / 'tests/fixtures/canonical_vectors_v1.json')
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    target = tmp_path / 'private_gold' / 'cases.json'
    target.parent.mkdir()
    target.write_text('{}')
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    problems, _ = checks(tmp_path)
    assert any('private gold' in problem.lower() for problem in problems)
