"""Create a deterministic source ZIP and manifest after offline package validation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import zipfile

from VERIFY_PACKAGE import MANIFEST, snapshot, source_files, verify
from scripts.check_package import checks


def build(root: Path, output: Path):
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    if root.resolve() in output.parents:
        raise ValueError('Place source ZIP outside the repository to avoid self-inclusion')
    issues, _ = checks(root)
    if issues:
        raise ValueError('\n'.join(issues))
    manifest = {'schema': 'caseproof.source-manifest.v1', 'package_version': '5.3.0.dev1',
                'sha256': snapshot(root), 'notice': 'Byte integrity only; not a signature, audit, or runtime guarantee.'}
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    issues, _ = verify(root)
    if issues:
        raise ValueError('\n'.join(issues))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        paths = sorted([*source_files(root), root / MANIFEST])
        for p in paths:
            name = root.name + '/' + p.relative_to(root).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    print(f'SOURCE_PACKAGE_CREATED: {len(paths)} files, {output.stat().st_size} bytes; {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output)


if __name__ == '__main__':
    main()
