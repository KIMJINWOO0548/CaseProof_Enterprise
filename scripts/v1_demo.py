"""Prepare or serve an explicit disposable local v1 demo; never print tokens."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4

from service.db import make_engine, session_factory
from service.workspace import ACTORS, ROOT, create_workspace_app, seed_workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--profile', type=Path, help='Restart this existing profile without resetting data')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if os.environ.get('CASEPROOF_DEMO_MODE') != '1':
        parser.error('CASEPROOF_DEMO_MODE=1 is required')
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    if args.profile:
        profile_path = args.profile.resolve()
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        # Restart only an existing file; never create a new database from a typo.
        db_path = Path(profile['database_path'])
        if not db_path.is_file():
            parser.error('Profile database does not exist; restart cannot initialize it')
    else:
        directory = ROOT / '.runtime' / ('v1-demo-' + uuid4().hex)
        directory.mkdir(parents=True, mode=0o700)
        db_path = directory / 'workspace.db'
        database_url = 'sqlite:///' + db_path.as_posix()
        env = dict(os.environ, CASEPROOF_V1_MIGRATION_MODE='disposable', CASEPROOF_V1_DATABASE_URL=database_url)
        subprocess.run([sys.executable, '-m', 'alembic', '-c', str(ROOT / 'alembic.ini'), 'upgrade', 'head'],
                       env=env, cwd=ROOT, check=True)
        engine = make_engine(database_url)
        try:
            with session_factory(engine).begin() as db:
                seed_workspace(db)
        finally:
            engine.dispose()
        tokens = {name: secrets.token_urlsafe(32) for name in ACTORS}
        registry = {hashlib.sha256(token.encode()).hexdigest(): {'tenant_id': 'fictional', 'actor_id': name}
                    for name, token in tokens.items()}
        profile = dict(database_path=str(db_path), tokens=tokens, registry=registry)
        profile_path = directory / 'profile.json'
        with profile_path.open('x', encoding='utf-8') as output:
            json.dump(profile, output, indent=2)
        profile_path.chmod(0o600)
    print('Profile: ' + str(profile_path))
    print('Workspace: http://127.0.0.1:' + str(args.port) + '/v1')
    if args.prepare_only:
        return
    import uvicorn
    engine = make_engine('sqlite:///' + db_path.as_posix())
    try:
        uvicorn.run(create_workspace_app(session_factory(engine), profile['registry']),
                    host='127.0.0.1', port=args.port, workers=1)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
