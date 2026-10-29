"""Verify source-package bytes; hashes are not a signature or a security certificate."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

MANIFEST = 'PACKAGE_MANIFEST_SHA256.json'
IGNORED_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.ruff_cache',
                '.mypy_cache', 'reports', 'build', 'dist', 'node_modules', 'archive', '.serena', '.runtime', 'current'}


def source_files(root: Path):
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(p in IGNORED_DIRS or p.endswith('.egg-info') for p in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink is not a release source file: {relative}')
        if path.is_file() and relative.as_posix() != MANIFEST and path.suffix not in {'.pyc', '.pyo'}:
            yield path


def snapshot(root: Path):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_files(root)}


def verify(root: Path):
    expected = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    if expected.get('schema') != 'caseproof.source-manifest.v1':
        raise ValueError('Unknown manifest schema')
    hashes = expected['sha256']
    if not isinstance(hashes, dict) or any(
        not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts
        or not isinstance(value, str) or len(value) != 64
        or any(c not in '0123456789abcdef' for c in value)
        for name, value in hashes.items()
    ):
        raise ValueError('Invalid manifest path or hash')
    actual = snapshot(root)
    issues = [f'missing: {p}' for p in sorted(hashes.keys() - actual.keys())]
    issues += [f'added: {p}' for p in sorted(actual.keys() - hashes.keys())]
    issues += [f'changed: {p}' for p in sorted(actual.keys() & hashes.keys()) if actual[p] != hashes[p]]
    return issues, len(actual)


def main():
    try:
        issues, count = verify(Path(__file__).resolve().parent)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'PACKAGE_VERIFY_FAIL: {exc}') from exc
    if issues:
        raise SystemExit('PACKAGE_VERIFY_FAIL\n' + '\n'.join(issues))
    print(f'PACKAGE_VERIFY_PASS: {count} source files; not a signature or security audit')


if __name__ == '__main__':
    main()
