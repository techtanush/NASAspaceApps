"""Strict tool dispatch with authorization before handlers and immutable receipts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, create_model

from analogforge.domain.policy import PolicyViolation
from analogforge.ports.catalog import TOOL_NAMES
from analogforge.ports.domain_models import MissionTestContract
from analogforge.ports.hashing import canonical_sha256
from analogforge.tools.allowlist import allowed_tools


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


FIELDS: dict[str, dict[str, Any]] = {
    "get_run_snapshot": {"sections": list[str]},
    "inspect_contract": {"contract_revision_id": UUID},
    "validate_mission_draft": {"draft": MissionTestContract},
    "validate_rover_profile": {"profile_revision_id": UUID},
    "resolve_dataset_coverage": {"subject_revision_id": UUID, "dataset_family": str, "measurement_kinds": list[str]},
    "fetch_dataset": {"product_id": str, "subject_revision_id": UUID, "selection_id": UUID},
    "characterize_target": {"target_revision_id": UUID, "measurement_spec_id": str, "source_evidence_ids": list[UUID]},
    "screen_earth_candidates": {
        "search_region_set_id": str,
        "target_profile_revision_id": UUID,
        "contract_revision_id": UUID,
        "max_candidates": int,
    },
    "analyze_earth_candidate": {
        "candidate_revision_id": UUID,
        "measurement_spec_id": str,
        "source_evidence_ids": list[UUID],
    },
    "compare_requirement": {
        "requirement_id": str,
        "candidate_revision_id": UUID,
        "target_profile_revision_id": UUID,
        "evidence_ids": list[UUID],
    },
    "assess_rover_compatibility": {
        "rover_revision_id": UUID,
        "candidate_revision_id": UUID,
        "test_revision_id": UUID | None,
        "evidence_ids": list[UUID],
    },
    "review_evidence_bundle": {"bundle_revision_id": UUID, "check_set": list[str]},
    "design_test": {
        "contract_revision_id": UUID,
        "rover_revision_id": UUID,
        "candidate_revision_id": UUID,
        "strategy": str,
        "waypoint_set_revision_id": UUID | None,
    },
    "search_route": {
        "test_revision_id": UUID,
        "search_config_revision_id": str,
        "exclusion_mask_revision_id": UUID | None,
    },
    "verify_route": {"test_revision_id": UUID, "route_revision_id": UUID},
    "diagnose_verification": {"result_revision_id": UUID},
    "optimize_portfolio": {"contract_revision_id": UUID, "candidate_revision_ids": list[UUID], "max_sites": int},
    "get_evidence": {"evidence_ids": list[UUID], "include": list[str]},
    "compare_evidence": {"left_evidence_id": UUID, "right_evidence_id": UUID, "comparison_kind": str},
    "build_passport_manifest": {
        "run_revision": int,
        "selected_candidate_revision_ids": list[UUID],
        "portfolio_revision_id": UUID | None,
    },
}
ARG_MODELS: dict[str, type[BaseModel]] = {
    name: cast(Any, create_model)(
        name + "Arguments", __base__=StrictArgs, **{key: (annotation, ...) for key, annotation in fields.items()}
    )
    for name, fields in FIELDS.items()
}


@dataclass
class ToolContext:
    role: str
    workspace_id: str
    run_id: str | None
    mode: str
    expected_revision: int
    contract_hash: str
    active: bool = True
    preparation: bool = False
    cancelled: bool = False
    current_revision: int | None = None
    current_contract_hash: str | None = None
    charge: Callable[[str], None] | None = None
    authorize: Callable[[str, dict[str, Any]], None] | None = None
    calls: dict[str, dict[str, Any]] = field(default_factory=dict)


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = {
        k: strict_schema(v)
        if isinstance(v, dict)
        else [strict_schema(i) if isinstance(i, dict) else i for i in v]
        if isinstance(v, list)
        else v
        for k, v in schema.items()
        if k not in {"default", "title"}
    }
    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
    return schema


class ToolRegistry:
    def __init__(self, handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        unknown = set(handlers) - set(TOOL_NAMES)
        if unknown:
            raise ValueError(f"Unknown tools: {unknown}")
        self.handlers = handlers

    def execute(self, name: str, arguments: dict[str, Any], context: ToolContext, *, call_id: str) -> dict[str, Any]:
        if name not in ARG_MODELS:
            raise PolicyViolation("TOOL_SCHEMA_UNAVAILABLE")
        parsed = ARG_MODELS[name].model_validate(arguments).model_dump(mode="json")
        if not context.active:
            raise PolicyViolation("INVOCATION_INACTIVE")
        if name not in allowed_tools(context.role, context.preparation):
            raise PolicyViolation("FORBIDDEN_TOOL", "INPUT_INVALID")
        if context.current_revision is not None and context.current_revision != context.expected_revision:
            raise PolicyViolation("STALE_REVISION", "REVISION_CONFLICT")
        if context.current_contract_hash is not None and context.current_contract_hash != context.contract_hash:
            raise PolicyViolation("FROZEN_INPUT_CHANGED")
        if context.cancelled:
            raise PolicyViolation("RUN_CANCELLED")
        if context.authorize is not None:
            context.authorize(name, parsed)
        if context.charge is not None:
            context.charge("tool_calls_per_invocation")
            context.charge("tool_calls_per_run")
        digest = canonical_sha256({"name": name, "arguments": parsed})
        if call_id in context.calls:
            if context.calls[call_id]["input_sha256"] != digest:
                raise PolicyViolation("TOOL_CALL_ID_REUSED")
            return dict(context.calls[call_id]["result"])
        if name not in self.handlers:
            raise PolicyViolation("TOOL_NOT_PERMITTED_IN_STAGE", "INPUT_INVALID")
        result = self.handlers[name](parsed)
        context.calls[call_id] = {"input_sha256": digest, "result": result}
        return result

    def schemas(self, role: str, preparation: bool = False) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": name,
                "description": f"Authorized {name}; returns registered evidence only.",
                "strict": True,
                "parameters": strict_schema(ARG_MODELS[name].model_json_schema()),
            }
            for name in sorted(allowed_tools(role, preparation))
            if name in ARG_MODELS
        ]
