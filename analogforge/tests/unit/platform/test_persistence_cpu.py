"""CPU deadline and cancellation cannot leave a worker child alive."""

import multiprocessing
import signal
import time
from typing import Any, NoReturn, cast

import pytest

from analogforge.db.store import PersistenceError
from analogforge.jobs.cpu import _stop_child, run_callable, run_science
from analogforge.ports.science import ScienceCancelled, ScienceContext, ScienceRequest, ScienceService


def _wait() -> str:
    time.sleep(10)
    return "late"


def _square(value: int) -> int:
    return value * value


def _ignore_sigterm(started: Any) -> NoReturn:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    started.set()
    while True:
        time.sleep(0.05)


def test_cpu_child_completes_and_timeout_reaps_process() -> None:
    assert run_callable(_square, 7) == 49
    before = {process.pid for process in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(PersistenceError) as error:
        run_callable(_wait, timeout_seconds=0.1)
    assert error.value.code == "TOOL_TIMEOUT"
    assert time.monotonic() - started < 5
    assert {process.pid for process in multiprocessing.active_children()} == before


def test_stubborn_child_is_killed_and_reaped_within_five_seconds() -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(target=_ignore_sigterm, args=(ready,), daemon=True)
    before = {child.pid for child in multiprocessing.active_children()}
    process.start()
    try:
        assert ready.wait(timeout=15), "Child did not install its SIGTERM handler"
        termination_requested = time.monotonic()
        _stop_child(process)
        assert time.monotonic() - termination_requested <= 5
        assert not process.is_alive()
        assert process.exitcode == -signal.SIGKILL
        assert {child.pid for child in multiprocessing.active_children()} == before
    finally:
        if process.is_alive():
            process.kill()
        process.join(timeout=1)
        process.close()


def test_already_cancelled_work_does_not_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    def cancelled() -> None:
        raise ScienceCancelled()

    def forbidden_context(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Cancelled work tried to create a subprocess")

    monkeypatch.setattr(multiprocessing, "get_context", forbidden_context)
    with pytest.raises(ScienceCancelled):
        run_science(
            cast(ScienceService, None),
            cast(ScienceRequest, None),
            cast(ScienceContext, None),
            check_cancelled=cancelled,
        )
