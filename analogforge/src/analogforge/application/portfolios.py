"""Project the science optimizer's assignments without aggregating joint rows."""

from typing import Any

from analogforge.domain.ids import envelope
from analogforge.ports.domain_models import CompositePortfolio


def assemble(
    workspace_id: str, run_id: str, mode: str, payload: dict[str, Any], window_ids: dict[str, str]
) -> dict[str, Any]:
    return CompositePortfolio.model_validate(
        {
            **envelope(workspace_id, run_id, mode),
            "candidate_ids": [window_ids[w] for w in payload["selected_window_ids"]],
            "requirement_assignments": [
                {
                    "requirement_id": a["requirement_id"],
                    "candidate_ids": [window_ids[w] for w in a["window_ids"]],
                    "coverage": a["coverage"],
                }
                for a in payload["assignments"]
            ],
            "objective_value": payload["objective_value"],
            "algorithm_id": payload["algorithm_id"],
            "residual_requirement_ids": payload["residual_requirement_ids"],
            "limitations": payload["limitations"],
        }
    ).model_dump(mode="json")
