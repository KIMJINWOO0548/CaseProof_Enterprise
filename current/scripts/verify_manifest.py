import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'reports'/'file_manifest_sha256.json').read_text(encoding='utf-8'))
errors=[]
for name,want in manifest['files'].items():
    path=root/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=want:
        errors.append(name)
print('FILE_MANIFEST_PASS' if not errors else 'FILE_MANIFEST_FAILED',
      f"{len(manifest['files'])-len(errors)}/{len(manifest['files'])} files")
if errors:print('\n'.join(errors));sys.exit(1)
