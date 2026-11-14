"""Render immutable passport formats under the active job lease."""

from typing import Any

from analogforge.application.exports import export_passport


def handle(runtime: Any, job: dict[str, Any]) -> None:
    export_passport(
        runtime.store,
        job["workspace_id"],
        job["payload"]["passport_id"],
        runtime.blobs,
        runtime.renderer,
        job_id=job["id"],
        lease_token=job["lease_token"],
    )
