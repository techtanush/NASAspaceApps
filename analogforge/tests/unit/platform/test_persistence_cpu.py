"""CPU deadline and cancellation cannot leave a worker child alive."""

from __future__ import annotations

import json
import multiprocessing
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn, cast
from uuid import uuid4

import pytest

from analogforge.db.store import PersistenceError
from analogforge.jobs.cpu import _stop_child, run_callable, run_science
from analogforge.ports.science import (
    ScienceCancelled,
    ScienceComputationResult,
    ScienceContext,
    ScienceRequest,
    ScienceService,
)


@pytest.mark.parametrize("deliver_result", [True, False])
def test_science_result_arriving_between_poll_and_child_exit_is_read(
    monkeypatch: pytest.MonkeyPatch, deliver_result: bool
) -> None:
    """Schedule the result after an empty poll, before the exit-state check."""
    from analogforge.ports.science_payloads import ResolveCoveragePayload

    result = ScienceComputationResult(
        request_id=uuid4(),
        operation="RESOLVE_COVERAGE",
        mode="synthetic",
        status="SUCCEEDED",
        algorithm_id="test",
        algorithm_version="1",
        parameters_sha256="0" * 64,
        input_sha256="0" * 64,
        payload=ResolveCoveragePayload(selections=[]),
    )
    ready = False
    received = False

    class Pipe:
        def poll(self, timeout: float = 0) -> bool:
            return ready

        def recv(self) -> tuple[str, Any]:
            nonlocal received
            assert ready
            received = True
            return "result", result.model_dump(mode="json")

        def close(self) -> None:
            pass

    class Process:
        def start(self) -> None:
            pass

        def is_alive(self) -> bool:
            nonlocal ready
            ready = deliver_result
            return False

        def join(self, timeout: float) -> None:
            pass

    class Context:
        def Pipe(self, **_kwargs: Any) -> tuple[Pipe, Pipe]:
            return Pipe(), Pipe()

        def Process(self, **_kwargs: Any) -> Process:
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda *_: Context())
    if deliver_result:
        actual = run_science(cast(ScienceService, None), cast(ScienceRequest, None), cast(ScienceContext, None))
        assert received
        assert actual == result
    else:
        with pytest.raises(PersistenceError, match="exited without a result") as error:
            run_science(cast(ScienceService, None), cast(ScienceRequest, None), cast(ScienceContext, None))
        assert error.value.code == "SYSTEM"
        assert not received


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


@pytest.mark.parametrize(
    "error_kind,expected_type",
    [
        ("key", "KeyError"),
        ("attribute", "AttributeError"),
        ("assertion", "AssertionError"),
    ],
)
def test_spawned_child_sanitizes_unexpected_error_without_stderr_leak(
    tmp_path: Path, error_kind: str, expected_type: str
) -> None:
    script = tmp_path / "child_error_probe.py"
    script.write_text("""import json
import multiprocessing
import sys
from analogforge.jobs.cpu import _child

class BrokenScience:
    def __init__(self, kind):
        self.kind = kind

    def execute(self, request, context):
        message = "PRIVATE_SOURCE_SENTINEL https://example.invalid/data?token=source-url-test-value"
        errors = {"key": KeyError(message), "attribute": AttributeError(message), "assertion": AssertionError(message)}
        raise errors[self.kind]

if __name__ == "__main__":
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(child, BrokenScience(sys.argv[1]), None, None, 2147483648))
    process.start()
    child.close()
    process.join(timeout=10)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)
        raise RuntimeError("Child did not exit")
    kind, payload = parent.recv()
    print(json.dumps({"kind": kind, "payload": payload, "child_exit": process.exitcode}))
    parent.close()
    process.close()
""")
    # Wait for normal child exit before reading its pipe, so cleanup cannot win
    # a race against multiprocessing's automatic traceback writer.
    result = subprocess.run(  # noqa: S603 - execute only this test's generated local probe
        [sys.executable, str(script), error_kind],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"kind": "error", "payload": expected_type, "child_exit": 0}
    assert result.stderr == ""
    assert "PRIVATE_SOURCE_SENTINEL" not in result.stdout + result.stderr
    assert "?token=source-url-test-value" not in result.stdout + result.stderr
