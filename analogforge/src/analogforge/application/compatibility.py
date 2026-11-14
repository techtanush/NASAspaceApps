"""Compatibility is a science receipt projection, never a second evaluator."""

from typing import Any

from analogforge.domain.ids import envelope


def assess(
    workspace_id: str,
    run_id: str,
    mode: str,
    candidate_id: str,
    payload: dict[str, Any],
    evidence_ids: list[str],
    rover_revision_id: str | None = None,
) -> dict[str, Any]:
    return {
        **envelope(workspace_id, run_id, mode),
        "candidate_id": candidate_id,
        "rover_revision_id": rover_revision_id or payload.get("rover_revision_id"),
        "preliminary": payload["preliminary"],
        "dimensions": [
            {
                "metric_id": row["metric_id"],
                "status": row["status"],
                "explanation": row["explanation"],
                "evidence_ids": [ref["evidence_id"] for ref in row["evidence"]],
            }
            for row in payload["dimensions"]
        ],
        "evidence_ids": evidence_ids,
        "payload": payload,
    }
