#!/usr/bin/env python3
"""Verify all entries listed in PACKAGE_MANIFEST_SHA256.json (run from package root)."""
from pathlib import Path
import json, hashlib, sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'PACKAGE_MANIFEST_SHA256.json').read_text(encoding='utf-8'))
files=manifest['files']
failed=[]
for rel, expected in files.items():
    path=root/rel
    if not path.is_file(): failed.append((rel,'MISSING'))
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=expected: failed.append((rel,'HASH_MISMATCH'))
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name not in {'PACKAGE_MANIFEST_SHA256.json'}}
extra=sorted(actual-set(files))
for rel in extra: failed.append((rel,'NOT_IN_MANIFEST'))
print('manifest_files=',len(files),'failures=',len(failed))
for rel,reason in failed[:50]: print(reason,rel)
sys.exit(bool(failed))
