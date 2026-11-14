"""Supervise only the private process groups started by this local dev command."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from analogforge.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def stop_services(processes: list[subprocess.Popen[bytes]], timeout: float = 10) -> None:
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            # A reaped launcher can leave a stale process-group id. Never signal
            # an unrelated group or prevent cleanup of our other live services.
            if process.poll() is None:
                raise
            continue
    deadline = time.monotonic() + timeout
    for process in processes:
        try:
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def main() -> int:
    settings = Settings()
    environment = {**os.environ, 'API_PORT': str(settings.api_port), 'WEB_PORT': str(settings.web_port),
                   'VITE_API_MOCK': '0'}
    commands = [([str(ROOT / '.venv/bin/analogforge'), 'serve'], ROOT),
                ([str(ROOT / '.venv/bin/analogforge'), 'worker'], ROOT)]
    if (ROOT / 'apps/web/package.json').is_file():
        commands.append((['corepack', 'pnpm', 'dev', '--host', '127.0.0.1'], ROOT / 'apps/web'))
    stopping = False
    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command, directory in commands:
            # Fixed application commands, validated public ports, isolated groups.
            processes.append(subprocess.Popen(command, cwd=directory, env=environment, start_new_session=True))  # noqa: S603
        print('AnalogForge development services started. Ctrl-C stops API, worker, and web.', flush=True)
        while not stopping:
            time.sleep(0.2)
            for process in processes:
                code = process.poll()
                if code is not None:
                    print(f'Development service exited: {process.pid} ({code})', file=sys.stderr)
                    return code or 1
        return 0
    finally:
        stop_services(processes)


if __name__ == '__main__':
    raise SystemExit(main())
