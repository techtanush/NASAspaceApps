"""Candidate-scoped process reuse retains per-request isolation and bounded failure cleanup."""

from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.db.store import PersistenceError
from analogforge.jobs.cpu import run_science, science_session
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    LocalScienceContext,
    ScienceCancelled,
    ScienceComputationResult,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import ResolveCoverageInput, ResolveCoveragePayload


class ProbeScience:
    def __init__(self, *, delay: float = 0, fail: bool = False, wrong_id: bool = False) -> None:
        self.delay, self.fail, self.wrong_id = delay, fail, wrong_id
        self.calls = 0

    def execute(self, request: ScienceRequest, context: LocalScienceContext) -> ScienceComputationResult:
        self.calls += 1
        context.scratch_dir().joinpath("request.json").write_text(json.dumps({
            "pid": os.getpid(), "request_id": str(request.request_id), "instance_calls": self.calls,
        }))
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("PRIVATE_PROVIDER_DETAIL")
        return ScienceComputationResult(
            request_id=uuid4() if self.wrong_id else request.request_id,
            operation=request.operation, mode=request.mode, status="SUCCEEDED",
            algorithm_id="session-probe", algorithm_version="1", parameters_sha256="0" * 64,
            input_sha256=canonical_sha256(request), payload=ResolveCoveragePayload(selections=[]),
        )


def request_context(tmp_path: Path) -> tuple[ScienceRequest, LocalScienceContext]:
    request = ScienceRequest(
        request_id=uuid4(), operation="RESOLVE_COVERAGE", mode="synthetic",
        inputs=ResolveCoverageInput(
            subject_kind="TARGET", adapter_id="synthetic_practice", measurement_kinds=["terrain"],
            aoi={"body": "MARS", "bbox": [137, -5, 138, -4], "longitude_convention": "NEG180_180",
                 "latitude_type": "PLANETOCENTRIC", "crs_wkt": None, "vertical_datum": "Unknown"},
        ),
        source_policy=SourcePolicy(policy_id="test", policy_sha256="0" * 64, allow_network=False),
    )
    context = LocalScienceContext(scratch=tmp_path / str(request.request_id), workspace_id=uuid4(), job_id=uuid4())
    return request, context


def probe(context: LocalScienceContext) -> dict[str, object]:
    return json.loads((context.scratch_dir() / "request.json").read_text())


def test_candidate_reuses_child_but_each_request_has_fresh_service_context_and_result(tmp_path: Path) -> None:
    before = {child.pid for child in multiprocessing.active_children()}
    first, one = request_context(tmp_path)
    second, two = request_context(tmp_path)
    service = ProbeScience()
    with science_session():
        result_one = run_science(service, first, one)
        result_two = run_science(service, second, two)
        assert probe(one)["pid"] == probe(two)["pid"]
        assert probe(one)["instance_calls"] == probe(two)["instance_calls"] == 1
        assert result_one.request_id == first.request_id and result_two.request_id == second.request_id
        assert result_one.input_sha256 == canonical_sha256(first)
        assert result_two.input_sha256 == canonical_sha256(second)
    assert service.calls == 0
    assert {child.pid for child in multiprocessing.active_children()} == before
    third, three = request_context(tmp_path)
    with science_session():
        run_science(service, third, three)
    assert probe(three)["pid"] != probe(one)["pid"]


@pytest.mark.parametrize("failure", ["timeout", "error", "identity", "cancelled", "midcancel"])
def test_failed_request_reaps_child_and_later_request_cannot_receive_stale_result(tmp_path: Path, failure: str) -> None:
    first, one = request_context(tmp_path)
    second, two = request_context(tmp_path)
    third, three = request_context(tmp_path)
    before = {child.pid for child in multiprocessing.active_children()}
    with science_session():
        run_science(ProbeScience(), first, one)

        checks = 0

        def cancelled() -> None:
            nonlocal checks
            checks += 1
            if failure == "cancelled" or checks >= 3:
                raise ScienceCancelled()

        started = time.monotonic()
        with pytest.raises(ScienceCancelled if failure in {"cancelled", "midcancel"} else PersistenceError) as error:
            run_science(
                ProbeScience(delay=2 if failure in {"timeout", "midcancel"} else 0,
                             fail=failure == "error", wrong_id=failure == "identity"),
                second, two, timeout_seconds=0.1 if failure == "timeout" else 30,
                check_cancelled=cancelled if failure in {"cancelled", "midcancel"} else None,
            )
        if failure not in {"cancelled", "midcancel"}:
            assert error.value.code == {"timeout": "TOOL_TIMEOUT", "error": "SYSTEM",
                                        "identity": "MODEL_OUTPUT_INVALID"}[failure]
        assert "PRIVATE_PROVIDER_DETAIL" not in str(error.value)
        assert time.monotonic() - started < 5
        assert {child.pid for child in multiprocessing.active_children()} == before
        result = run_science(ProbeScience(), third, three)
        assert result.request_id == third.request_id and probe(three)["pid"] != probe(one)["pid"]
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_per_request_memory_budget_change_starts_a_new_child(tmp_path: Path) -> None:
    first, one = request_context(tmp_path)
    second, two = request_context(tmp_path)
    with science_session():
        run_science(ProbeScience(), first, one, memory_bytes=2147483648)
        run_science(ProbeScience(), second, two, memory_bytes=1073741824)
    assert probe(one)["pid"] != probe(two)["pid"]


@pytest.mark.parametrize("cancel", [False, True])
def test_blocked_request_producer_does_not_disable_timeout_or_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool,
) -> None:
    """A cold/unresponsive child that never reads its pipe must remain interruptible."""
    blocked, released, finished = threading.Event(), threading.Event(), threading.Event()

    class Pipe:
        def send(self, _payload: object) -> None:
            blocked.set()
            released.wait(timeout=10)
            finished.set()

        def poll(self, timeout: float) -> bool:
            time.sleep(timeout)
            return False

        def close(self) -> None:
            released.set()

    class Process:
        alive = True

        def start(self) -> None:
            pass

        def is_alive(self) -> bool:
            return self.alive

        def terminate(self) -> None:
            self.alive = False
            released.set()

        def join(self, timeout: float) -> None:
            pass

        def close(self) -> None:
            pass

    class Context:
        def Pipe(self, **_kwargs: object) -> tuple[Pipe, Pipe]:
            # Closing the parent's copy of the child endpoint cannot release its send.
            return Pipe(), type("ChildPipe", (), {"close": lambda _self: None})()

        def Process(self, **_kwargs: object) -> Process:
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda *_args: Context())
    request, context = request_context(tmp_path)

    def check_cancelled() -> None:
        if cancel and blocked.is_set():
            raise ScienceCancelled()

    started = time.monotonic()
    with science_session(), pytest.raises(ScienceCancelled if cancel else PersistenceError):
        run_science(ProbeScience(), request, context, timeout_seconds=0.05, check_cancelled=check_cancelled)
    assert blocked.is_set() and finished.is_set()
    assert time.monotonic() - started < 2
