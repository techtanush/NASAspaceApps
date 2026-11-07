"""Receipt envelope conversion keeps scientific status distinct from transport status."""

from typing import Any


def execution_result(receipt: dict[str, Any], payload: dict[str, Any] | None, tool_call_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "tool_call_id": tool_call_id,
        "receipt_id": receipt["id"],
        "tool_name": receipt["tool_name"],
        "tool_version": receipt["tool_version"],
        "status": receipt["status"],
        "runtime_mode": receipt["mode"],
        "input_hash": receipt["input_sha256"],
        "output_hash": receipt["output_sha256"],
        "evidence_ids": receipt["evidence_ids"],
        "artifact_ids": [],
        "result": payload,
        "error": None
        if receipt["error_code"] is None
        else {
            "code": receipt["error_code"],
            "detail_code": None,
            "message": "See registered computation issues",
            "retryable": False,
            "retry_after_seconds": None,
            "affected_requirement_ids": [],
        },
        "job_id": None,
    }
