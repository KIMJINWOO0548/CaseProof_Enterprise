"""Run local checks with a bounded workaround for Windows socketpair error 10014.

Usage: python -m scripts.windows_checks pytest -q
Only socketpair initialization is retried; application requests/assertions are not.
This does not modify the installed Python runtime or the running service.
"""
import runpy
import socket
import sys
import time


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m scripts.windows_checks MODULE [ARGS...]')
    original = socket.socketpair
    retries = 0

    def socketpair(*args, **kwargs):
        nonlocal retries
        for attempt in range(128):
            try:
                return original(*args, **kwargs)
            except OSError as exc:
                if getattr(exc, 'winerror', None) != 10014 or attempt == 127:
                    raise
                retries += 1
                time.sleep(0.02)

    if sys.platform == 'win32':
        socket.socketpair = socketpair
    module, *args = sys.argv[1:]
    sys.argv = [module, *args]
    try:
        runpy.run_module(module, run_name='__main__', alter_sys=True)
    finally:
        socket.socketpair = original
        print(f'Windows socketpair initialization retries: {retries}')


if __name__ == '__main__':
    main()
