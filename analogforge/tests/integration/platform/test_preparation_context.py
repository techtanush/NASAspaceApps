"""Preparation is durable and separately scoped before any scientific run exists."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretStr

from analogforge.application import missions
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.jobs.handlers.prepare_fingerprint import (
    PreparationRoleResult,
    PreparationTask,
    PreparationToolReceipt,
    handle,
)
from analogforge.main import PlatformRuntime
from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.settings import Settings
from tests.integration.platform.test_journey_api import FIXTURES, journey_store
from tests.integration.platform.test_migrations import platform_store

__all__ = ["journey_store", "platform_store"]


@pytest.fixture
def preparation(journey_store: Store, tmp_path: Path) -> dict[str, Any]:
    workspace = str(uuid4())
    journey_store.ensure_workspace(workspace)
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    seed_synthetic(None, settings)
    runtime = PlatformRuntime(settings, journey_store)
    content = json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())
    draft = {field: content[field] for field in ("name", "objective", "target", "requirements", "assumptions")}
    with journey_store.transaction(workspace) as unit:
        header = missions.create(unit, workspace, draft)
        record = unit.create(
            "preparations",
            {"mission_draft_revision_id": header["current_draft_id"], "mode": "synthetic", "status": "QUEUED"},
        )
    return {"runtime": runtime, "workspace": workspace, "header": header, "record": record, "draft": draft}


def dispatch(preparation: dict[str, Any]) -> dict[str, Any]:
    runtime = preparation["runtime"]
    with runtime.store.transaction(preparation["workspace"]) as unit:
        payload = {
            "mission_id": preparation["header"]["id"],
            "expected_revision": preparation["header"]["revision"],
            "mode": preparation["record"]["mode"],
            "rover_revision_id": None,
        }
        job = unit.enqueue("PREPARE_FINGERPRINT", payload, preparation_id=preparation["record"]["id"])
    leased = runtime.store.claim_job(workspace_id=preparation["workspace"])
    assert leased and leased["id"] == job["id"]
    handle(runtime, leased)
    return dict(leased)


@pytest.mark.db
@pytest.mark.parametrize("case", ["generated_observable", "generated_rule", "supplied_unknown"])
def test_live_preparation_rejects_invented_measurements_but_preserves_user_unknowns(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    runtime, workspace = preparation["runtime"], preparation["workspace"]
    supplied = case == "supplied_unknown"
    requirement = {
        **preparation["draft"]["requirements"][0],
        "origin": "USER",
        "observable": "user_instrument_observable" if supplied else "unique_slope_exposure_m",
        "parameters": {
            **preparation["draft"]["requirements"][0]["parameters"],
            "comparison_rule_id": "user-rule-v1" if supplied else None,
        },
    }
    source = {
        "name": "Live terrain draft", "objective": "Compare measured terrain without assuming waypoint locations",
        "target": {**preparation["draft"]["target"], "vertical_datum": "MOLA areoid"},
        "requirements": [requirement] if supplied else [],
        "assumptions": ["User supplied source scope"],
    }
    proposal = runtime.engine.prepare({**source, "id": str(uuid4()), "requirements": [requirement]}, workspace)
    if case == "generated_observable":
        proposal["requirements"][0]["observable"] = "no_rover_experiment"
    elif case == "generated_rule":
        proposal["requirements"][0]["parameters"]["comparison_rule_id"] = "scope-exclusion-v1"
    else:
        # The model may not replace the user's unsupported row with a supported one.
        proposal["requirements"][0]["observable"] = "unique_slope_exposure_m"
        proposal["requirements"][0]["parameters"]["comparison_rule_id"] = None
    with runtime.store.transaction(workspace) as unit:
        header = missions.create(unit, workspace, source)
        record = unit.create(
            "preparations",
            {"mission_draft_revision_id": header["current_draft_id"], "mode": "live", "status": "QUEUED"},
        )
    runtime.settings.openai_api_key = SecretStr("local-test-only")
    runtime.settings.openai_model = "test-model"
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        calls.append(json.loads(kwargs["input"]))
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)},
        ]}]}

    monkeypatch.setattr(runtime.engine, "_provider_client", lambda: SimpleNamespace(create=create))
    selected: list[str] = []
    real_scenario = runtime.engine._scenario

    def scenario(identifier: str) -> dict[str, Any]:
        selected.append(identifier)
        return dict(real_scenario(identifier))

    monkeypatch.setattr(runtime.engine, "_scenario", scenario)
    dispatch({**preparation, "header": header, "record": record})
    assert selected == [catalog.SCENARIO_LIVE_HACKATHON]
    assert calls[0]["mode"] == "live" and "example_structure" not in calls[0]
    with runtime.store.transaction(workspace) as unit:
        result = unit.require("preparations", record["id"])
        invocation = unit.list("agent_invocations", {"preparation_id": record["id"]})[0]
        if supplied:
            assert result["status"] == "SUCCEEDED"
            revision = unit.require("mission_revisions", result["proposed_revision_id"])
            assert revision["requirements"] == source["requirements"]
            assert revision["assumptions"] == source["assumptions"]
            assert revision["accepted_at"] is None
        else:
            assert result["status"] == "FAILED" and result["error"]["code"] == "MODEL_OUTPUT_INVALID"
            assert unit.list("mission_revisions") == []
            assert invocation["role_result"]["payload"]["proposed_contract"] is None
        assert unit.list("mission_acceptances") == []


@pytest.mark.db
def test_preparation_scoped_invocation_real_validation_and_atomic_proposal(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace = preparation["runtime"], preparation["workspace"]
    real_prepare = runtime.engine.prepare
    calls: list[str] = []

    def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # This second connection can lock the preparation during generation. The
        # dispatch charge and RUNNING invocation must already have committed.
        with runtime.store.transaction(workspace) as unit:
            unit.connection.execute(sa.text("SET LOCAL lock_timeout='200ms'"))
            row = unit.require("preparations", preparation["record"]["id"], lock=True)
            assert row["budget"]["counters"]["preparation_model_requests"] == 1
            invocations = unit.list("agent_invocations", {"preparation_id": row["id"]})
            assert len(invocations) == 1 and invocations[0]["status"] == "RUNNING"
            assert invocations[0]["run_id"] is None
        calls.append("dispatch")
        return dict(real_prepare(*args, **kwargs))

    monkeypatch.setattr(runtime.engine, "prepare", generate)
    job = dispatch(preparation)
    assert calls == ["dispatch"]
    with runtime.store.transaction(workspace) as unit:
        result = unit.require("preparations", preparation["record"]["id"])
        assert result["status"] == "SUCCEEDED"
        assert unit.require("jobs", job["id"])["state"] == "SUCCEEDED"
        revision = unit.require("mission_revisions", result["proposed_revision_id"])
        assert revision["accepted_at"] is None
        header = unit.require("missions", preparation["header"]["id"])
        assert header["accepted_contract_id"] is None
        assert unit.list("mission_acceptances") == []
        assert (
            unit.list("runs") == unit.list("evidence") == unit.list("tool_receipts") == unit.list("role_results") == []
        )
        invocation = unit.list("agent_invocations", {"preparation_id": result["id"]})[0]
        task = PreparationTask.model_validate(invocation["task"])
        assert task.run_id is None and str(task.preparation_id) == result["id"]
        assert invocation["run_id"] is None and invocation["usage_json"]["model_dispatches"] == 1
        role = PreparationRoleResult.model_validate(invocation["role_result"])
        assert str(role.payload.proposed_contract.id) == revision["id"]
        receipts = [PreparationToolReceipt.model_validate(value) for value in invocation["preparation_receipts"]]
        assert [receipt.tool_name for receipt in receipts] == ["validate_mission_draft", "submit_role_result"]
        assert all(receipt.run_id is None and receipt.status == "SUCCEEDED" for receipt in receipts)
        assert role.payload.validation_receipt_id == receipts[0].id
        assert role.payload.acceptance_required
        assert "run_id" not in role.model_dump()
        assert (
            canonical_sha256({key: invocation[key] for key in ("role_result", "preparation_receipts", "source_sha256")})
            == invocation["sealed_sha256"]
        )


@pytest.mark.db
def test_preparation_dispatch_cap_survives_new_jobs_and_safe_failures(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace = preparation["runtime"], preparation["workspace"]
    calls: list[int] = []
    private_response_text = "a provider-private response that must never be persisted"

    def failed(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        raise RuntimeError(private_response_text)

    monkeypatch.setattr(runtime.engine, "prepare", failed)
    for _ in range(4):
        dispatch(preparation)
    replacement_store = Store(runtime.store.engine.url.render_as_string(hide_password=False))
    replacement = PlatformRuntime(runtime.settings, replacement_store)
    monkeypatch.setattr(replacement.engine, "prepare", failed)
    try:
        dispatch({**preparation, "runtime": replacement})
    finally:
        replacement_store.close()
    assert len(calls) == 4
    with runtime.store.transaction(workspace) as unit:
        record = unit.require("preparations", preparation["record"]["id"])
        assert record["status"] == "BLOCKED" and record["error"]["code"] == "BUDGET_EXHAUSTED"
        assert record["budget"]["counters"]["preparation_model_requests"] == 4
        invocations = unit.list("agent_invocations", {"preparation_id": record["id"]})
        assert len(invocations) == 4 and all(row["status"] == "FAILED" for row in invocations)
        assert all(row["preparation_receipts"] == [] for row in invocations)
        assert all(row["role_result"]["payload"]["proposed_contract"] is None for row in invocations)
        assert unit.list("mission_revisions") == []
        assert private_response_text not in json.dumps(invocations)


@pytest.mark.db
@pytest.mark.parametrize("change", ["mission", "cancel", "lease"])
def test_changed_or_cancelled_preparation_cannot_publish_a_proposal(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    runtime, workspace = preparation["runtime"], preparation["workspace"]
    real_prepare: Callable[..., Any] = runtime.engine.prepare

    def altered(*args: Any, **kwargs: Any) -> dict[str, Any]:
        proposal = dict(real_prepare(*args, **kwargs))
        with runtime.store.transaction(workspace) as unit:
            if change == "mission":
                header = unit.require("missions", preparation["header"]["id"])
                missions.save_draft(
                    unit,
                    header["id"],
                    {
                        "expected_revision": header["revision"],
                        "draft": {**preparation["draft"], "objective": "A changed user objective"},
                    },
                )
            elif change == "cancel":
                record = unit.require("preparations", preparation["record"]["id"])
                unit.replace("preparations", record["id"], {**record, "status": "CANCELLED"})
            else:
                unit.connection.execute(
                    sa.text("""UPDATE jobs SET lease_expires_at=now()-interval '1 second'
                    WHERE preparation_id=:id AND state='RUNNING'"""),
                    {"id": preparation["record"]["id"]},
                )
        return proposal

    monkeypatch.setattr(runtime.engine, "prepare", altered)
    dispatch(preparation)
    with runtime.store.transaction(workspace) as unit:
        assert unit.list("mission_revisions") == []
        assert unit.list("mission_acceptances") == []
        invocation = unit.list("agent_invocations", {"preparation_id": preparation["record"]["id"]})[0]
        assert invocation.get("output_json") is None
        assert invocation["status"] == ("RUNNING" if change == "lease" else "FAILED")
        record = unit.require("preparations", preparation["record"]["id"])
        assert record["budget"]["counters"]["preparation_model_requests"] == 1
        if change == "cancel":
            assert record["status"] == "CANCELLED"


@pytest.mark.db
def test_preparation_semantic_tool_rejects_invalid_proposed_requirement(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = preparation["runtime"]
    real_prepare = runtime.engine.prepare

    def invalid(*args: Any, **kwargs: Any) -> dict[str, Any]:
        proposed = dict(real_prepare(*args, **kwargs))
        proposed["requirements"] = [
            *proposed["requirements"],
            {
                **proposed["requirements"][0],
                "id": "R-INVALID-PROPOSED",
                "operator": "GTE",
                "lower": None,
                "upper": None,
            },
        ]
        return proposed

    monkeypatch.setattr(runtime.engine, "prepare", invalid)
    dispatch(preparation)
    with runtime.store.transaction(preparation["workspace"]) as unit:
        record = unit.require("preparations", preparation["record"]["id"])
        assert record["status"] == "FAILED" and record["error"]["code"] == "MODEL_OUTPUT_INVALID"
        assert unit.list("mission_revisions") == []
        invocation = unit.list("agent_invocations", {"preparation_id": record["id"]})[0]
        assert len(invocation["preparation_receipts"]) == 1
        receipt = invocation["preparation_receipts"][0]
        assert receipt["tool_name"] == "validate_mission_draft" and receipt["status"] == "FAILED"
        assert receipt["input_sha256"] and receipt["output_sha256"]
        assert invocation["role_result"]["payload"]["proposed_contract"] is None


@pytest.mark.db
def test_changed_queued_draft_stops_before_charging_or_dispatching(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace = preparation["runtime"], preparation["workspace"]
    with runtime.store.transaction(workspace) as unit:
        header = unit.require("missions", preparation["header"]["id"])
        missions.save_draft(
            unit, header["id"], {"expected_revision": header["revision"], "draft": preparation["draft"]}
        )
    attempted: list[int] = []

    def forbidden(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        attempted.append(1)
        raise AssertionError("Stale input reached the model")

    monkeypatch.setattr(runtime.engine, "prepare", forbidden)
    job = dispatch(preparation)
    assert attempted == []
    with runtime.store.transaction(workspace) as unit:
        assert unit.list("agent_invocations", {"preparation_id": preparation["record"]["id"]}) == []
        assert unit.require("jobs", job["id"])["error"]["code"] == "REVISION_CONFLICT"
        assert unit.require("preparations", preparation["record"]["id"])["status"] == "FAILED"


@pytest.mark.db
@pytest.mark.parametrize("case", ["valid", "json_generation_correction", "invalid_json", "budget_exhausted"])
def test_preparation_groq_fallback_counts_actual_requests_and_retains_acceptance_gate(
    preparation: dict[str, Any], monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    import httpx

    from tests.unit.platform.test_groq_fallback import configured, response

    runtime, workspace = preparation["runtime"], preparation["workspace"]
    proposal = runtime.engine.prepare({**preparation["draft"], "id": str(uuid4())}, workspace)
    runtime.settings.openai_api_key = SecretStr("primary-marker")
    runtime.settings.openai_model = "primary-model"
    runtime.settings.groq_api_key = SecretStr("secondary-marker")
    runtime.settings.groq_model = "secondary-model"
    runtime.settings.groq_fallback_enabled = True
    with runtime.store.transaction(workspace) as unit:
        record = unit.require("preparations", preparation["record"]["id"])
        record["mode"] = "live"
        if case == "budget_exhausted":
            record["budget"] = {"counters": {"preparation_model_requests": 3}}
        unit.replace("preparations", record["id"], record)
    preparation["record"] = record

    generated_count = []

    def proposed_response(body: dict[str, Any]) -> httpx.Response:
        generated_count.append(True)
        if case == "json_generation_correction" and len(generated_count) == 1:
            return httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "Rejected JSON"}})
        text = "{" if case == "invalid_json" else json.dumps(proposal)
        return httpx.Response(200, json=response(body, [{
            "type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }]))

    client, seen = configured(groq_handler=proposed_response)
    monkeypatch.setattr(runtime.engine, "_provider_client", lambda: client)
    dispatch(preparation)
    with runtime.store.transaction(workspace) as unit:
        saved = unit.require("preparations", record["id"])
        invocation = unit.list("agent_invocations", {"preparation_id": record["id"]})[0]
        expected = 1 if case == "budget_exhausted" else (3 if case == "json_generation_correction" else 2)
        assert len(seen) == len(invocation["provider_attempts"]) == expected
        assert invocation["usage_json"]["model_dispatches"] == expected
        assert saved["budget"]["counters"]["preparation_model_requests"] == (
            4 if case == "budget_exhausted" else expected
        )
        assert invocation["provider"] == ("openai" if case == "budget_exhausted" else "groq")
        assert invocation["model"] == ("primary-model" if case == "budget_exhausted" else "secondary-model")
        assert saved["status"] == {
            "valid": "SUCCEEDED", "json_generation_correction": "SUCCEEDED",
            "invalid_json": "FAILED", "budget_exhausted": "BLOCKED",
        }[case]
        if case in {"valid", "json_generation_correction"}:
            revision = unit.require("mission_revisions", saved["proposed_revision_id"])
            assert revision["accepted_at"] is None
        else:
            assert saved["error"]["code"] == (
                "BUDGET_EXHAUSTED" if case == "budget_exhausted" else "MODEL_OUTPUT_INVALID"
            )
            assert unit.list("mission_revisions") == []
        assert unit.list("mission_acceptances") == []
        assert unit.list("runs") == unit.list("evidence") == []
