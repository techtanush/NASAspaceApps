"""Idle database outages must not take down the durable worker process."""

import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import InterfaceError, OperationalError

from analogforge.jobs.worker import Worker


@pytest.mark.parametrize("error_type", [OperationalError, InterfaceError])
def test_worker_survives_a_transient_connection_error_without_logging_credentials(error_type, caplog):
    worker = Worker(MagicMock(), lambda _: None)
    calls = []

    def once():
        calls.append(True)
        if len(calls) == 1:
            raise error_type("secret database statement", {}, Exception("private-connection-password"))
        worker.stop()
        return False

    worker.run_once = once
    worker.run_forever(poll_seconds=0)
    assert len(calls) == 2
    assert "worker.database_unavailable" in caplog.text
    assert "private-connection-password" not in caplog.text
    assert "secret database statement" not in caplog.text


def test_signal_stop_never_waits_on_the_idle_event_lock(tmp_path):
    marker = tmp_path / "stopped"
    script = (
        "from pathlib import Path; from analogforge.jobs.worker import Worker; "
        "w=Worker(None,lambda _:None)\n"
        "with w.stopping._cond:\n"
        " w.stop()\n"
        " assert w.run_once() is False\n"
        f" Path({str(marker)!r}).write_text('stopped')\n"
    )
    child = subprocess.Popen([sys.executable, "-c", script])  # noqa: S603
    try:
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        assert marker.is_file(), "A stop signal deadlocked while the idle loop held the event lock"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
