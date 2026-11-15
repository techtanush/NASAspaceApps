"""Bounded POSIX worker subprocess execution with prompt cancellation."""

from __future__ import annotations

import multiprocessing
import resource
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
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

_active_session: ContextVar[ScienceSession | None] = ContextVar("science_process_session", default=None)


def _stop_child(process: BaseProcess) -> None:
    """Bound termination to one second of grace plus one second after SIGKILL."""
    if process.is_alive():
        process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)
    if process.is_alive():
        raise PersistenceError("SYSTEM", "CPU child could not be stopped within its termination budget")


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
    except Exception as exc:  # noqa: BLE001 - child boundary sends only a sanitized exception type
        connection.send(("error", type(exc).__name__))
    finally:
        connection.close()


def _session_child(connection: Connection, memory_bytes: int) -> None:
    """One candidate's sequential requests; only import/config caches survive each call."""
    try:
        if resource.getrlimit(resource.RLIMIT_AS)[0] != 0 and __import__("sys").platform != "darwin":
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        while True:
            try:
                service, request, context = connection.recv()
            except EOFError:
                return
            result = None
            try:
                result = service.execute(request, context)
                connection.send(("result", result.model_dump(mode="json")))
                if result.status == "FAILED":
                    return
            except ScienceCancelled:
                connection.send(("cancelled", "ScienceCancelled"))
                return
            except ScienceDeadlineExceeded:
                connection.send(("deadline", "ScienceDeadlineExceeded"))
                return
            except Exception as exc:  # noqa: BLE001 - no private child exception text crosses the boundary
                connection.send(("error", type(exc).__name__))
                return
            finally:
                # Do not retain any request context, service instance or result between operations.
                del service, request, context, result
    finally:
        connection.close()


class ScienceSession:
    """A bounded candidate-scoped child, with independent deadlines and cancellation per request."""

    def __init__(self) -> None:
        self.process: BaseProcess | None = None
        self.connection: Connection | None = None
        self.memory_bytes: int | None = None

    def close(self) -> None:
        process, connection = self.process, self.connection
        self.process = self.connection = None
        try:
            if process is not None:
                _stop_child(process)
                process.close()
        finally:
            if connection is not None:
                connection.close()

    def run(
        self, service: ScienceService, request: ScienceRequest, context: ScienceContext,
        timeout_seconds: float, memory_bytes: int, check_cancelled: Callable[[], None] | None,
    ) -> ScienceComputationResult:
        sender: threading.Thread | None = None
        try:
            if check_cancelled is not None:
                check_cancelled()
            if self.process is not None and (not self.process.is_alive() or self.memory_bytes != memory_bytes):
                self.close()
            if self.process is None:
                parent, child = multiprocessing.get_context("spawn").Pipe(duplex=True)
                process = multiprocessing.get_context("spawn").Process(
                    target=_session_child, args=(child, memory_bytes), daemon=True
                )
                try:
                    process.start()
                except BaseException:
                    parent.close()
                    raise
                finally:
                    child.close()
                self.process, self.connection, self.memory_bytes = process, parent, memory_bytes
            assert self.process is not None and self.connection is not None
            deadline = time.monotonic() + timeout_seconds
            connection = self.connection
            send_failed = threading.Event()

            def send_request() -> None:
                try:
                    connection.send((service, request, context))
                except Exception:  # noqa: BLE001 - serializer/pipe errors contain no public exception text
                    send_failed.set()

            # Cold child imports and a large request can fill the pipe. Keep deadline
            # and cancellation checks running while serialization/transmission waits.
            sender = threading.Thread(target=send_request, daemon=True)
            sender.start()
            while True:
                if check_cancelled is not None:
                    check_cancelled()
                if time.monotonic() >= deadline:
                    raise PersistenceError("TOOL_TIMEOUT", "Science CPU deadline exceeded")
                if send_failed.is_set():
                    raise PersistenceError("SYSTEM", "Science request could not be sent to the subprocess")
                if self.connection.poll(0.1):
                    try:
                        kind, payload = self.connection.recv()
                    except EOFError as exc:
                        raise PersistenceError("SYSTEM", "Science subprocess exited without a result") from exc
                    if kind == "cancelled":
                        raise ScienceCancelled()
                    if kind == "deadline":
                        raise ScienceDeadlineExceeded()
                    if kind != "result":
                        raise PersistenceError("SYSTEM", f"Science subprocess failed ({payload})")
                    result = ScienceComputationResult.model_validate(payload)
                    if (result.request_id, result.operation, result.mode) != (
                        request.request_id, request.operation, request.mode
                    ):
                        raise PersistenceError("MODEL_OUTPUT_INVALID", "Science subprocess result identity mismatch")
                    if result.status == "FAILED":
                        self.close()
                    return result
                if not self.process.is_alive() and not self.connection.poll():
                    raise PersistenceError("SYSTEM", "Science subprocess exited without a result")
        except BaseException:
            self.close()
            raise
        finally:
            if sender is not None:
                sender.join(timeout=1)


@contextmanager
def science_session() -> Iterator[None]:
    """Reuse one spawned child only within an explicit candidate boundary, then reap it."""
    session = ScienceSession()
    token = _active_session.set(session)
    try:
        yield
    finally:
        _active_session.reset(token)
        session.close()


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
    session = _active_session.get()
    if session is not None:
        return session.run(service, request, context, timeout_seconds, memory_bytes, check_cancelled)
    if check_cancelled is not None:
        check_cancelled()
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
            # A child can send and exit between poll() and is_alive(). Its
            # buffered result must be drained before treating exit as failure.
            if not process.is_alive() and not parent.poll():
                raise PersistenceError("SYSTEM", "Science subprocess exited without a result")
    finally:
        try:
            _stop_child(process)
        finally:
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
        try:
            _stop_child(process)
        finally:
            parent.close()


def _callable_child(connection: Connection, function: Callable[..., Any], args: tuple[Any, ...]) -> None:
    connection.send(function(*args))
    connection.close()
