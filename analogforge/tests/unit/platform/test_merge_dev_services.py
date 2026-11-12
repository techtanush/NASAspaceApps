"""MRG-07: terminating the launcher must also terminate its frontend descendants."""

import os
import runpy
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock


def test_dev_cleanup_terminates_nested_service_processes(tmp_path):
    module = runpy.run_path(str(Path(__file__).parents[3] / 'scripts/dev_services.py'))
    child_pid = tmp_path / 'child.pid'
    # Publish readiness atomically; file existence must mean its PID is complete.
    # The fixture parent also reaps its child after the group signal, keeping
    # the original PID-disappearance assertion independent of launchd timing.
    script = """
import signal, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
def stop(_signum, _frame):
    child.wait(timeout=5)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
marker = Path(sys.argv[1])
pending = marker.with_name(marker.name + ".tmp")
pending.write_text(str(child.pid))
pending.replace(marker)
time.sleep(60)
"""
    process = subprocess.Popen([sys.executable, '-c', script, str(child_pid)], start_new_session=True)  # noqa: S603
    try:
        deadline = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert child_pid.is_file(), 'Nested service must actually have started'
        nested = int(child_pid.read_text())
        module['stop_services']([process])
        assert process.poll() is not None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(nested, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            raise AssertionError('Nested service survived development shutdown')
    finally:
        module['stop_services']([process])


def test_exited_service_permission_race_does_not_prevent_other_owned_cleanup(monkeypatch):
    module = runpy.run_path(str(Path(__file__).parents[3] / 'scripts/dev_services.py'))
    exited, live = MagicMock(pid=999999981), MagicMock(pid=999999982)
    exited.poll.return_value = 0
    signal_group = MagicMock(side_effect=[PermissionError(), None])
    monkeypatch.setattr(os, 'killpg', signal_group)
    module['stop_services']([exited, live])
    assert signal_group.call_count == 2
    live.wait.assert_called_once()
