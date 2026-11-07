"""CPU deadline and cancellation cannot leave a worker child alive."""

import multiprocessing
import time

import pytest

from analogforge.db.store import PersistenceError
from analogforge.jobs.cpu import run_callable


def _wait() -> str:
    time.sleep(10)
    return "late"


def _square(value: int) -> int:
    return value * value


def test_cpu_child_completes_and_timeout_reaps_process() -> None:
    assert run_callable(_square, 7) == 49
    before = {process.pid for process in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(PersistenceError) as error:
        run_callable(_wait, timeout_seconds=0.1)
    assert error.value.code == "TOOL_TIMEOUT"
    assert time.monotonic() - started < 5
    assert {process.pid for process in multiprocessing.active_children()} == before
