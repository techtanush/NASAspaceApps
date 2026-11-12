"""Idle database outages must not take down the durable worker process."""

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
