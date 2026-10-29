#!/usr/bin/env bash
set -euo pipefail
node -e "const fs=require('fs');const s=fs.readFileSync('service/static/index.html','utf8');const m=s.match(/<script>([\s\S]*?)<\/script>/);if(!m)throw Error('script missing');fs.writeFileSync('/tmp/caseproof-v5-ui.js',m[1])"
node --check /tmp/caseproof-v5-ui.js
printf 'UI_JS_SYNTAX_PASS\n'
