"""Replaceable worker coordinator; handlers publish only through lease-fenced transactions."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError

from analogforge.db.store import LeaseLost, PersistenceError, Store
from analogforge.jobs.queue import HEARTBEAT_SECONDS, LEASE_SECONDS
from analogforge.jobs.reaper import Reaper
from analogforge.ports.science import ScienceCancelled, ScienceDeadlineExceeded

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        store: Store,
        handler: Callable[[dict[str, Any]], None],
        lease_seconds: int = LEASE_SECONDS,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
    ) -> None:
        if heartbeat_seconds <= 0 or heartbeat_seconds >= lease_seconds:
            raise ValueError("Heartbeat interval must be positive and shorter than the lease")
        self.store, self.handler = store, handler
        self.lease_seconds, self.heartbeat_seconds = lease_seconds, heartbeat_seconds
        self.stopping = threading.Event()
        self._stop_requested = False
        self.worker_id = str(uuid4())
        self.reaper = Reaper(store)
        self._last_presence = 0.0

    def stop(self) -> None:
        """Stop claiming; the current bounded handler completes or loses its lease."""
        # CLI signal handlers run on the idle loop's thread. Event.set() can
        # deadlock if that signal interrupts Event.wait() while its lock is held.
        self._stop_requested = True

    def run_once(self) -> bool:
        if self._stop_requested or self.stopping.is_set():
            return False
        if time.monotonic() - self._last_presence >= self.heartbeat_seconds:
            self.store.record_worker_heartbeat(self.worker_id)
            self._last_presence = time.monotonic()
        self.reaper.run_due()
        job = self.store.claim_job(lease_seconds=self.lease_seconds)
        if job is None:
            return False
        done, lost = threading.Event(), threading.Event()
        heartbeat_thread = threading.Thread(target=self._heartbeats, args=(job, done, lost), daemon=True)
        heartbeat_thread.start()
        error_code: str | None = None
        try:
            self.handler(job)
        except ScienceCancelled:
            error_code = "RUN_CANCELLED"
        except ScienceDeadlineExceeded:
            error_code = "TOOL_TIMEOUT"
        except PersistenceError as exc:
            error_code = exc.code
        except (OSError, RuntimeError, ValueError, TypeError, SQLAlchemyError) as exc:
            error_code = str(getattr(exc, "code", "SYSTEM"))
            logger.error("worker.handler_failed", extra={"job_id": job["id"], "error_type": type(exc).__name__})
        except Exception as exc:  # noqa: BLE001 - process boundary records failure without message or traceback
            error_code = "SYSTEM"
            logger.error("worker.handler_failed", extra={"job_id": job["id"], "error_type": type(exc).__name__})
        finally:
            done.set()
            heartbeat_thread.join(timeout=self.heartbeat_seconds + 1)
        if error_code == "RUN_CANCELLED":
            if job.get("run_id"):
                self.store.cancel_run(job["workspace_id"], job["run_id"])
                with self.store.transaction(job["workspace_id"]) as unit:
                    unit.require("runs", job["run_id"], lock=True)
                    current = unit.require("jobs", job["id"], lock=True)
                    if current.get("lease_token") == job["lease_token"] and current["state"] == "RUNNING":
                        unit.replace("jobs", current["id"], {**current, "state": "CANCELLED"})
            else:
                with self.store.transaction(job["workspace_id"]) as unit:
                    preparation = unit.require("preparations", job["preparation_id"], lock=True)
                    current = unit.require("jobs", job["id"], lock=True)
                    if current["lease_token"] == job["lease_token"]:
                        unit.replace("preparations", preparation["id"], {**preparation, "status": "CANCELLED"})
                        unit.replace("jobs", current["id"], {**current, "state": "CANCELLED"})
            return True
        if lost.is_set() or error_code == "LEASE_LOST":
            logger.warning("worker.publication_fenced", extra={"job_id": job["id"], "code": error_code or "LEASE_LOST"})
            return True
        with self.store.transaction(job["workspace_id"]) as unit:
            # A durable stage can complete its own job together with the successor.
            if unit.require("jobs", job["id"])["state"] in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}:
                return True
        try:
            with self.store.publication(job["workspace_id"], job["id"], job["lease_token"]) as unit:
                current = unit.require("jobs", job["id"], lock=True)
                blocked = error_code in {
                    "TOOL_TIMEOUT",
                    "SOURCE_UNAVAILABLE",
                    "PROVIDER_AUTH_FAILED",
                    "PROVIDER_RATE_LIMITED",
                    "SCIENCE_FACADE_MISSING",
                    "RENDERER_MISSING",
                }
                current["state"] = "SUCCEEDED" if error_code is None else "BLOCKED" if blocked else "FAILED"
                if error_code is not None:
                    current["error"] = {"code": error_code}
                unit.replace("jobs", job["id"], current)
                if error_code is not None and current.get("run_id"):
                    run = unit.require("runs", current["run_id"], lock=True)
                    if run["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                        unit.append_event(
                            run["id"], "job.failed", {"code": error_code, "job_id": current["id"]}, run["mode"]
                        )
                    else:
                        previous_state = run["state"]
                        run["state"] = "BLOCKED" if blocked else "FAILED"
                        if blocked:
                            run.setdefault("runtime", {})["resume_state"] = previous_state
                            run["blocked_dependencies"] = sorted(
                                set(run.get("blocked_dependencies", []) + [error_code])
                            )
                        unit.replace("runs", run["id"], run, run["revision"])
                        unit.append_event(
                            run["id"], "run.blocked" if blocked else "run.failed", {"code": error_code}, run["mode"]
                        )
                elif error_code is not None and current.get("preparation_id"):
                    preparation = unit.require("preparations", current["preparation_id"], lock=True)
                    unit.replace(
                        "preparations",
                        preparation["id"],
                        {**preparation, "status": current["state"], "error": {"code": error_code}},
                    )
        except (LeaseLost, PersistenceError) as exc:
            logger.warning("worker.finalize_fenced", extra={"job_id": job["id"], "code": exc.code})
        return True

    def _heartbeats(self, job: dict[str, Any], done: threading.Event, lost: threading.Event) -> None:
        while not done.wait(self.heartbeat_seconds):
            try:
                owned = self.store.heartbeat_job(job["id"], job["lease_token"], self.lease_seconds)
                if owned:
                    self.store.record_worker_heartbeat(self.worker_id)
            except (OSError, RuntimeError, SQLAlchemyError) as exc:
                logger.error("worker.heartbeat_failed", extra={"job_id": job["id"], "error_type": type(exc).__name__})
                lost.set()
                return
            if not owned:
                lost.set()
                return

    def run_forever(self, poll_seconds: float = 1) -> None:
        while not (self._stop_requested or self.stopping.is_set()):
            try:
                worked = self.run_once()
            except (OperationalError, InterfaceError) as exc:
                # Committed work and lease ownership remain in PostgreSQL. Reconnect on the
                # next poll; an interrupted stage must still reclaim its lease before publishing.
                logger.warning("worker.database_unavailable", extra={"error_type": type(exc).__name__})
                worked = False
            if not worked:
                self.stopping.wait(poll_seconds)
