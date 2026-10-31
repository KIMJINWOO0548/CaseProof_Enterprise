import pytest
from scripts import windows_checks


def test_socketpair_burst_retries_initialization_without_repeating_module(monkeypatch):
    calls = {'initialization': 0, 'module': 0}
    def initialize():
        calls['initialization'] += 1
        if calls['initialization'] <= 70:
            error = OSError('synthetic Windows startup burst')
            error.winerror = 10014
            raise error
        return 'ready'
    def run(*args, **kwargs):
        calls['module'] += 1
        assert windows_checks.socket.socketpair() == 'ready'
    monkeypatch.setattr(windows_checks.socket, 'socketpair', initialize)
    monkeypatch.setattr(windows_checks.sys, 'platform', 'win32')
    monkeypatch.setattr(windows_checks.sys, 'argv', ['windows_checks', 'synthetic_module'])
    monkeypatch.setattr(windows_checks.time, 'sleep', lambda _: None)
    monkeypatch.setattr(windows_checks.runpy, 'run_module', run)
    windows_checks.main()
    assert calls == {'initialization': 71, 'module': 1}
    assert windows_checks.socket.socketpair is initialize


def test_other_errors_are_never_retried(monkeypatch):
    calls = []
    def initialize():
        calls.append('initialization')
        raise OSError('different error')
    monkeypatch.setattr(windows_checks.socket, 'socketpair', initialize)
    monkeypatch.setattr(windows_checks.sys, 'platform', 'win32')
    monkeypatch.setattr(windows_checks.sys, 'argv', ['windows_checks', 'synthetic_module'])
    monkeypatch.setattr(windows_checks.runpy, 'run_module', lambda *a, **k: windows_checks.socket.socketpair())
    with pytest.raises(OSError, match='different error'):
        windows_checks.main()
    assert calls == ['initialization']
