"""The documented launcher serves an existing disposable profile over real loopback HTTP."""
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time

import httpx
import pytest
from alembic import command
from alembic.config import Config

from service.db import make_engine, session_factory
from service.workspace import ROOT, seed_workspace


def test_windows_listener_retries_only_initialization_and_closes_failed_socket(monkeypatch):
    from scripts import v1_demo
    sockets = []
    class Listener:
        closed = False
        def bind(self, address):
            assert address == ('127.0.0.1', 8766)
        def listen(self, backlog):
            assert backlog == 128
            if len(sockets) == 1:
                error = OSError('synthetic first-listen failure')
                error.winerror = 10014
                raise error
        def close(self):
            self.closed = True
    def create(*_):
        listener = Listener()
        sockets.append(listener)
        return listener
    with monkeypatch.context() as patch:
        patch.setattr(v1_demo.sys, 'platform', 'win32')
        patch.setattr(v1_demo.socket, 'socket', create)
        patch.setattr(v1_demo.time, 'sleep', lambda _: None)
        listener = v1_demo._listener(8766, 128)
    assert len(sockets) == 2 and sockets[0].closed and not listener.closed
    listener.close()


@pytest.mark.parametrize('platform,code,attempts', [('win32', 10014, 128), ('win32', 10048, 1), ('linux', 10014, 1)])
def test_listener_initialization_is_bounded_and_other_errors_are_not_retried(monkeypatch, platform, code, attempts):
    from scripts import v1_demo
    sockets, delays = [], []
    class Listener:
        closed = False
        def bind(self, _):
            error = OSError('synthetic bind failure')
            error.winerror = code
            raise error
        def close(self):
            self.closed = True
    def create(*_):
        listener = Listener()
        sockets.append(listener)
        return listener
    with monkeypatch.context() as patch:
        patch.setattr(v1_demo.sys, 'platform', platform)
        patch.setattr(v1_demo.socket, 'socket', create)
        patch.setattr(v1_demo.time, 'sleep', delays.append)
        with pytest.raises(OSError):
            v1_demo._listener(8766, 128)
    assert len(sockets) == attempts and all(listener.closed for listener in sockets)
    assert delays == [0.02] * (attempts - 1)


def test_real_demo_cli_starts_and_preserves_existing_database(tmp_path, monkeypatch):
    database = tmp_path / 'workspace.db'
    url = 'sqlite:///' + database.as_posix()
    monkeypatch.setenv('CASEPROOF_DEMO_MODE', '1')
    monkeypatch.setenv('CASEPROOF_V1_MIGRATION_MODE', 'disposable')
    monkeypatch.setenv('CASEPROOF_V1_DATABASE_URL', url)
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    engine = make_engine(url)
    try:
        with session_factory(engine).begin() as db:
            seed_workspace(db)
    finally:
        engine.dispose()
    original_digest = hashlib.sha256(database.read_bytes()).hexdigest()
    token = secrets.token_urlsafe(32)
    profile = tmp_path / 'profile.json'
    profile.write_text(json.dumps({'database_path': str(database), 'registry': {
        hashlib.sha256(token.encode()).hexdigest(): {'tenant_id': 'fictional', 'actor_id': 'analyst'}}}), encoding='utf-8')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    log_path = tmp_path / 'server.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-u', '-m', 'scripts.windows_checks', 'scripts.v1_demo',
            '--profile', str(profile), '--port', str(port)], cwd=ROOT, env=dict(os.environ),
            stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=1, trust_env=False) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    assert process.poll() is None, log_path.read_text(encoding='utf-8')
                    try:
                        response = client.get('/api/v1/workspace', headers={'Authorization': 'Bearer ' + token})
                    except httpx.TransportError:
                        time.sleep(0.05)
                        continue
                    assert response.status_code == 200, response.text
                    catalog = response.json()['data']
                    assert catalog['actor']['actor_id'] == 'analyst' and len(catalog['presets']) == 3
                    break
                else:
                    raise AssertionError('Launcher did not reach authenticated HTTP readiness within20s')
                assert client.get('/api/v1/workspace').status_code == 401
                page = client.get('/v1')
                assert page.status_code == 200 and 'CaseProof' in page.text
                javascript = client.get('/static/v1.js')
                assert javascript.status_code == 200 and 'RequestClient' in javascript.text
        finally:
            if process.poll() is None:
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, check=True)
                else:
                    process.terminate()
            process.wait(timeout=10)
    assert token.encode() not in log_path.read_bytes()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original_digest
