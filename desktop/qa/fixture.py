"""Windows QA fixture with real SQLite v1 API and one controlled reply loss."""

import argparse
import asyncio
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import urlsplit
from uuid import uuid4

import uvicorn

from scripts.v1_demo import _listener
from service.db import make_engine, session_factory
from service.models_v1 import SuiteSnapshot
from service.repositories import add_payload, decode
from service.workspace import ACTORS, ROOT, create_workspace_app, seed_workspace


def store_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data), encoding='utf-8')
    temporary.replace(path)


def seed_desktop_review_suite(db, workspace):
    preset = deepcopy(next(item for item in workspace['presets'] if item['id'] == 'lantern'))
    body = preset['create_body']
    original = decode(db.get(SuiteSnapshot, ('fictional', body['suite_version_id'])))
    base = preset['case_inputs'][0]
    names = ['qa-1-window-failed', 'qa-2-context-uncertain', 'qa-3-base-pass', 'qa-4-observed-pass']
    preset.update(id='qa-review-cases', label='합성 감사 검토 · 네 가지 사례',
                  case_inputs=[dict(deepcopy(base), case_id=name) for name in names])
    body['suite_version_id'] = str(uuid4())
    policy_versions = original['case_policy_versions'][base['case_id']]
    add_payload(db, SuiteSnapshot, dict(original, id=body['suite_version_id'], required_case_ids=names,
        workspace=preset, case_policy_versions={name: policy_versions for name in names},
        coverage_by_case={name: [] for name in names}))


async def serve_until_stopped(server, backend, stop_file):
    async def watch_stop():
        while not stop_file.exists():
            await asyncio.sleep(0.1)
        server.should_exit = True

    watcher = asyncio.create_task(watch_stop())
    try:
        await server.serve(sockets=[backend])
    finally:
        watcher.cancel()


def serve(practice):
    database = practice / 'qa.sqlite3'
    if database.exists():
        raise RuntimeError('The QA directory must be disposable and empty of database files.')
    database_url = 'sqlite:///' + database.as_posix()
    env = dict(os.environ, CASEPROOF_V1_MIGRATION_MODE='disposable', CASEPROOF_V1_DATABASE_URL=database_url)
    subprocess.run([sys.executable, '-m', 'alembic', '-c', str(ROOT / 'alembic.ini'), 'upgrade', 'head'],
                   cwd=ROOT, env=env, check=True)
    engine = make_engine(database_url)
    db_sessions = session_factory(engine)
    with db_sessions.begin() as db:
        seed_desktop_review_suite(db, seed_workspace(db))
    tokens = {actor: secrets.token_hex(24) for actor in ACTORS}
    registry = {hashlib.sha256(token.encode()).hexdigest(): {'tenant_id': 'fictional', 'actor_id': actor}
                for actor, token in tokens.items()}
    app = create_workspace_app(db_sessions, registry)
    release_flag = practice / 'drop-next-release'
    events = practice / 'http-events.jsonl'
    trace_lock = Lock()
    with _listener(0, 128) as backend:
        port = backend.getsockname()[1]

        class Proxy(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_args):
                pass

            def forward(self):
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or not (
                        parsed.path == '/v1' or parsed.path.startswith('/api/v1/')):
                    self.send_error(404)
                    return
                length = int(self.headers.get('Content-Length', 0))
                if not 0 <= length <= 2_000_000:
                    self.send_error(413)
                    return
                forwarded = {k: v for k, v in self.headers.items()
                             if k.lower() not in {'host', 'connection', 'transfer-encoding', 'accept-encoding'}}
                connection = HTTPConnection('127.0.0.1', port, timeout=15)
                try:
                    connection.request(self.command, self.path, self.rfile.read(length) if length else None,
                                       headers=forwarded)
                    result = connection.getresponse()
                    content = result.read()
                    status_code = result.status
                    content_type = result.getheader('Content-Type', 'application/json')
                finally:
                    connection.close()
                path = parsed.path
                idempotency_key = self.headers.get('Idempotency-Key')
                if path.startswith('/api/v1/mutations/'):
                    idempotency_key = path.rsplit('/', 1)[1]
                    path = '/api/v1/mutations/{key}'
                with trace_lock:
                    dropped = (self.command == 'POST' and path.endswith('/release-decision') and
                               status_code == 200 and release_flag.exists())
                    if dropped:
                        release_flag.unlink()
                    record = {'method': self.command, 'path': path, 'status': status_code, 'dropped': dropped}
                    if idempotency_key:
                        record['key_sha256'] = hashlib.sha256(idempotency_key.encode()).hexdigest()
                    with events.open('a', encoding='utf-8') as trace:
                        trace.write(json.dumps(record) + '\n')
                if dropped:
                    # The backend has already produced its durable result.
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                self.send_response(status_code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(content)

            do_GET = forward
            do_POST = forward

        with ThreadingHTTPServer(('127.0.0.1', 0), Proxy, bind_and_activate=False) as proxy:
            proxy.socket.close()
            proxy.socket = _listener(0, 128)
            proxy.server_address = proxy.socket.getsockname()
            worker = Thread(target=proxy.serve_forever, name='qa-only-reply-loss', daemon=True)
            worker.start()
            try:
                store_json(practice / 'fixture.json', {'url': f'http://127.0.0.1:{proxy.server_address[1]}',
                                                       'tokens': tokens})
                config = uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='warning')
                server = uvicorn.Server(config)
                windows_loop = asyncio.SelectorEventLoop if sys.platform == 'win32' else None
                with asyncio.Runner(loop_factory=windows_loop) as runner:
                    runner.run(serve_until_stopped(server, backend, practice / 'stop-fixture'))
            finally:
                proxy.shutdown()
                worker.join()
                engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('practice', type=Path)
    args = parser.parse_args()
    os.environ['CASEPROOF_DEMO_MODE'] = '1'
    serve(args.practice.resolve(strict=True))


if __name__ == '__main__':
    main()
