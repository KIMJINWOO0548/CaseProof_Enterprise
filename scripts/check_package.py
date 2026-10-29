"""Offline structural checks for the public source handoff, not security certification."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from VERIFY_PACKAGE import source_files

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['README.md', 'START_HERE.md', 'AGENTS.md', 'LICENSE', 'NOTICE',
            'CONTRIBUTING.md', 'SECURITY.md', 'CODE_OF_CONDUCT.md', 'THIRD_PARTY_NOTICES.md',
            'pyproject.toml', 'requirements.lock', 'requirements-dev.lock',
            '.github/workflows/ci.yml', 'docs/STATUS.md', 'docs/VALIDATION.md',
            'prebuild/08_IMPLEMENTATION_CONTRACTS.md', 'contracts/README.md']


def checks(root=ROOT):
    problems = [f'Missing required file: {name}' for name in REQUIRED if not (root / name).is_file()]
    paths = list(source_files(root))
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if p.name in {'.env', 'tokens.json', 'credentials.json', 'token-registry.json'} or p.suffix.lower() in {
            '.sqlite', '.sqlite3', '.db', '.pem', '.key', '.p12', '.apk', '.zip', '.docx', '.pdf', '.whl'
        } or any(part in {'private', 'holdout-private', 'private_gold'} for part in p.relative_to(root).parts):
            problems.append(f'Non-public runtime/private/binary file: {rel}')
        if p.suffix.lower() in {'.md', '.py', '.json', '.toml', '.yaml', '.yml', '.txt', '.lock'}:
            text = p.read_text(encoding='utf-8')
            if re.search(r'cpdemo_[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
                problems.append(f'Possible credential/private key in {rel}; manually inspect')
            if p.suffix == '.md':
                for raw in re.findall(r'(?<!!)\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
                    dest = unquote(raw.split('#', 1)[0])
                    if not dest or urlparse(dest).scheme or dest.startswith('//'):
                        continue
                    target = (p.parent / dest).resolve()
                    if root.resolve() not in (target, *target.parents) or not target.exists():
                        problems.append(f'Broken/outside Markdown link {rel}: {raw}')
    folder = root / 'contracts'
    schemas = list(folder.glob('*.schema.json'))
    registry = Registry()
    for p in schemas:
        value = json.loads(p.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(value)
        resource = Resource.from_contents(value)
        registry = registry.with_resource(p.as_uri(), resource)
        if '$id' in value:
            registry = registry.with_resource(value['$id'], resource)
    records = json.loads((folder / 'examples/index.json').read_text(encoding='utf-8'))['examples']
    for record in records:
        name, _, fragment = record['schema'].partition('#')
        file = (folder / name).resolve()
        ref = file.as_uri() + (('#' + fragment) if fragment else '')
        validator = Draft202012Validator({'$ref': ref}, registry=registry, format_checker=FormatChecker())
        data = json.loads((folder / record['file']).read_text(encoding='utf-8'))
        actual = validator.is_valid(data)
        if actual != record['valid']:
            problems.append(f'Wrong expected schema result: {record["file"]}')
    vectors = json.loads((root / 'tests/fixtures/canonical_vectors_v1.json').read_text(encoding='utf-8'))['vectors']
    for v in vectors:
        if 'canonical_utf8_hex' not in v:
            continue
        canonical = bytes.fromhex(v['canonical_utf8_hex'])
        original = json.dumps(v['input'], ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if canonical != original or hashlib.sha256(('caseproof:' + v['purpose'] + ':v1\n').encode() + canonical).hexdigest() != v['hash']:
            problems.append(f'Canonical golden-vector mismatch: {v["id"]}')
    return problems, {'source_files': len(paths), 'schemas': len(schemas), 'examples': len(records), 'canonical_vectors': len(vectors)}


def main():
    problems, counts = checks()
    if problems:
        raise SystemExit('PACKAGE_CHECK_FAIL\n' + '\n'.join(problems))
    print('PACKAGE_CHECK_PASS ' + json.dumps(counts, sort_keys=True))
    print('Target schemas are PLANNED; this check does not implement /api/v1 or certify security.')


if __name__ == '__main__':
    main()
