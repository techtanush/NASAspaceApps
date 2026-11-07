"""Bounded POSIX worker subprocess execution with prompt cancellation."""

from __future__ import annotations

import multiprocessing
import resource
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

from analogforge.db.store import PersistenceError
from analogforge.ports.science import (
    ScienceCancelled,
    ScienceComputationResult,
    ScienceContext,
    ScienceDeadlineExceeded,
    ScienceRequest,
    ScienceService,
)


def _child(
    connection: Connection, service: ScienceService, request: ScienceRequest, context: ScienceContext, memory_bytes: int
) -> None:
    try:
        # RLIMIT_AS is reliable on Linux. macOS uses parent wall-time + worker container limits.
        if resource.getrlimit(resource.RLIMIT_AS)[0] != 0 and __import__("sys").platform != "darwin":
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        result = service.execute(request, context)
        connection.send(("result", result.model_dump(mode="json")))
    except ScienceCancelled:
        connection.send(("cancelled", "ScienceCancelled"))
    except ScienceDeadlineExceeded:
        connection.send(("deadline", "ScienceDeadlineExceeded"))
    except (RuntimeError, ValueError, OSError, MemoryError, TypeError) as exc:
        connection.send(("error", type(exc).__name__))
    finally:
        connection.close()


def run_science(
    service: ScienceService,
    request: ScienceRequest,
    context: ScienceContext,
    timeout_seconds: float = 30,
    memory_bytes: int = 2147483648,
    check_cancelled: Callable[[], None] | None = None,
) -> ScienceComputationResult:
    if timeout_seconds <= 0 or memory_bytes <= 0:
        raise ValueError("CPU budgets must be positive")
    # Spawn avoids inheriting DB sockets or locks from the lease-heartbeat thread.
    # The worker passes the stateless facade and an immutable artifact/path context.
    parent, child = multiprocessing.get_context("spawn").Pipe(duplex=False)
    process = multiprocessing.get_context("spawn").Process(
        target=_child, args=(child, service, request, context, memory_bytes), daemon=True
    )
    process.start()
    child.close()
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            if check_cancelled is not None:
                check_cancelled()
            if parent.poll(0.1):
                try:
                    kind, payload = parent.recv()
                except EOFError as exc:
                    raise PersistenceError("SYSTEM", "Science subprocess exited without a result") from exc
                if kind == "cancelled":
                    raise ScienceCancelled()
                if kind == "deadline":
                    raise ScienceDeadlineExceeded()
                if kind != "result":
                    raise PersistenceError("SYSTEM", f"Science subprocess failed ({payload})")
                return ScienceComputationResult.model_validate(payload)
            if time.monotonic() >= deadline:
                raise PersistenceError("TOOL_TIMEOUT", "Science CPU deadline exceeded")
            if not process.is_alive():
                raise PersistenceError("SYSTEM", "Science subprocess exited without a result")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        parent.close()


def run_callable(function: Callable[..., Any], *args: Any, timeout_seconds: float = 30) -> Any:
    """Test/operational helper for bounded non-scientific CPU work."""
    parent, child = multiprocessing.get_context("spawn").Pipe(duplex=False)
    process = multiprocessing.get_context("spawn").Process(
        target=_callable_child, args=(child, function, args), daemon=True
    )
    process.start()
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            raise PersistenceError("TOOL_TIMEOUT", "CPU deadline exceeded")
        return parent.recv()
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        parent.close()


def _callable_child(connection: Connection, function: Callable[..., Any], args: tuple[Any, ...]) -> None:
    connection.send(function(*args))
    connection.close()
