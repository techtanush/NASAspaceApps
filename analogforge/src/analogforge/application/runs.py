"""Run admission pins accepted inputs before scheduling asynchronous work."""

from __future__ import annotations

import importlib
from typing import Any

from analogforge.api.errors import ApiError
from analogforge.application.datasets import DatasetError, read_lock
from analogforge.application.missions import accepted_contract, now, uid
from analogforge.ports.domain_models import RunSnapshot
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.passport_renderer import PassportRenderer
from analogforge.ports.science import ScienceOperation, ScienceService, SourcePolicy


def load_entry_point(path: str, error_code: str) -> Any:
    module, name = path.split(":", 1)
    try:
        factory = getattr(importlib.import_module(module), name)
        return factory()
    except Exception as exc:
        raise ApiError(
            error_code,
            "The required component is not installed or does not conform.",
            503,
            details={"dependency": path},
        ) from exc


def require_live(settings: Any, mode: str) -> None:
    if mode != "live":
        return
    for field, env in [("openai_api_key", "OPENAI_API_KEY"), ("openai_model", "OPENAI_MODEL")]:
        if not getattr(settings, field, None):
            raise ApiError(
                "PROVIDER_AUTH_FAILED",
                "Configure the required live model dependency.",
                503,
                details={"dependency": env, "remediation": f"Set {env} in the server environment."},
            )


def create(
    uow: Any,
    workspace_id: str,
    body: dict[str, Any],
    settings: Any,
    scenarios: dict[str, Any],
    science: Any = None,
    renderer: Any = None,
) -> dict[str, Any]:
    require_live(settings, body["mode"])
    contract = accepted_contract(uow, body["mission_revision_id"])
    if contract["accepted_at"] is None:
        raise ApiError("CONTRACT_NOT_ACCEPTED", "Accept the displayed mission revision before running.", 409)
    rover = uow.require("rover_revisions", body["rover_revision_id"]) if body["rover_revision_id"] else None
    scenario = scenarios.get(body["scenario_config_id"])
    if scenario is None:
        raise ApiError("INPUT_INVALID", "Unknown scenario configuration.")
    if body["mode"] not in scenario["allowed_modes"]:
        raise ApiError(
            "INVALID_TRANSITION",
            "The requested scenario is unavailable in this mode.",
            409,
            details={"dependency": body["scenario_config_id"]},
        )
    if scenario["body"] != contract["target"]["body"]:
        raise ApiError("INPUT_INVALID", "The scenario and mission target bodies differ.")
    if body["dataset_lock_id"] != scenario["default_dataset_lock_id"]:
        raise ApiError("INPUT_INVALID", "Use the scenario's frozen dataset policy lock.")
    lock_path = settings.data_root / "locks" / f"{body['dataset_lock_id']}.json"
    if not lock_path.is_file():
        raise ApiError(
            "SOURCE_UNAVAILABLE",
            "The selected dataset policy has not been locked.",
            503,
            details={"dependency": body["dataset_lock_id"]},
        )
    try:
        lock = read_lock(settings, body["dataset_lock_id"])
    except (DatasetError, ValueError, OSError, KeyError) as exc:
        raise ApiError(
            getattr(exc, "code", "SOURCE_CHECKSUM_MISMATCH"),
            "The selected source-policy lock or its dataset bytes failed validation.",
            409,
        ) from exc
    selectors = [s for s in (
        scenario["target_source"], scenario["earth_source"], *scenario.get("additional_sources", {}).values()
    ) if s is not None]
    local_ids = [s["dataset_id"] for s in selectors if s["kind"] == "LOCAL_DATASET"]
    fixture_ids = [s["fixture_id"] for s in selectors if s["kind"] == "SYNTHETIC_FIXTURE"]
    locked_ids = {entry["dataset_id"] for entry in lock["datasets"]}
    if not set(local_ids).issubset(locked_ids) or not set(fixture_ids).issubset(lock.get("synthetic_fixture_ids", [])):
        raise ApiError("MODE_MISMATCH", "The selected sources are outside the pinned dataset policy.", 409)
    if body["mode"] == "live" and (fixture_ids or lock.get("synthetic_fixture_ids")):
        raise ApiError("MODE_MISMATCH", "Live investigations require non-synthetic source datasets.", 409)
    source_policy = SourcePolicy(
        policy_id=body["dataset_lock_id"],
        policy_sha256=lock["policy_sha256"],
        allowed_adapter_ids=["local_dataset"] if local_ids else ["synthetic_practice"],
        local_dataset_ids=local_ids,
        synthetic_fixture_ids=fixture_ids,
        allow_network=bool(lock["allow_network"]) and body["mode"] == "live",
    ).model_dump(mode="json")
    if science is None:
        science = load_entry_point("analogforge.science.facade:create_science_service", "SCIENCE_FACADE_MISSING")
    if not isinstance(science, ScienceService) or science.supported_operations() != frozenset(ScienceOperation):
        raise ApiError("SCIENCE_FACADE_MISSING", "The science entry point does not satisfy the frozen port.", 503)
    if renderer is None:
        renderer = load_entry_point("analogforge.rendering.passport:create_passport_renderer", "RENDERER_MISSING")
    if not isinstance(renderer, PassportRenderer) or not renderer.renderer_version:
        raise ApiError("RENDERER_MISSING", "The renderer entry point does not satisfy the frozen port.", 503)
    run_id = uid()
    snapshot = RunSnapshot.model_validate(
        {
            "schema_version": "1.0",
            "id": run_id,
            "run_id": run_id,
            "workspace_id": workspace_id,
            "mode": body["mode"],
            "created_at": now(),
            "state": "VALIDATING",
            "revision": 1,
            "last_event_seq": 0,
            "mission_revision_id": contract["id"],
            "rover_revision_id": rover["id"] if rover else None,
            "target_profile_id": None,
            "candidate_ids": [],
            "qualification_ids": [],
            "test_ids": [],
            "test_result_ids": [],
            "portfolio_ids": [],
            "passport_id": None,
            "pending_review": None,
            "blocked_dependencies": [],
            "config_sha256": canonical_sha256(scenario),
            "selected_candidate_id": None,
            "selected_portfolio_id": None,
            "scenario_config_id": body["scenario_config_id"],
            "dataset_lock_id": body["dataset_lock_id"],
        }
    ).model_dump(mode="json")
    stored = {
        **snapshot,
        "runtime": {
            "mission_content_sha256": contract["content_sha256"],
            "rover_content_sha256": rover["content_sha256"] if rover else None,
            "scenario": scenario,
            "source_policy": source_policy,
            "dataset_policy_sha256": lock["policy_sha256"],
            "budgets": {},
        },
    }
    uow.create("runs", stored)
    job = uow.enqueue("ADVANCE_RUN", {"run_id": run_id}, run_id=run_id)
    uow.append_event(
        run_id, "run.state_changed", {"summary": "Accepted inputs pinned; investigation queued."}, body["mode"]
    )
    current = uow.require("runs", run_id)
    return {"run_id": run_id, "job_id": job["id"], "command_id": uid(), "revision": current["revision"]}
