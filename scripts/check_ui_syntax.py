"""Check every inline JavaScript block without a shared temporary filename."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required for the UI syntax check; check NOT RUN')
    root = Path(__file__).resolve().parents[1]
    source = (root / 'service/static/index.html').read_text(encoding='utf-8')
    blocks = re.findall(r'<script\b[^>]*>(.*?)</script>', source, flags=re.S | re.I)
    if not blocks:
        raise SystemExit('No inline JavaScript found')
    with tempfile.TemporaryDirectory(prefix='caseproof_js_') as folder:
        for index, block in enumerate(blocks):
            script = Path(folder) / f'inline_{index}.js'
            script.write_text(block, encoding='utf-8')
            subprocess.run([node, '--check', str(script)], check=True)
    print(f'UI_JS_SYNTAX_PASS: {len(blocks)} script(s); browser execution is a separate check')


if __name__ == '__main__':
    main()
