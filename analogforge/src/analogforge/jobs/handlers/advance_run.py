"""Advance a single fenced workflow checkpoint."""

from typing import Any


def handle(runtime: Any, job: dict[str, Any]) -> None:
    runtime.engine.advance(
        job["payload"]["run_id"], job["workspace_id"], job_id=job["id"], lease_token=job["lease_token"]
    )
