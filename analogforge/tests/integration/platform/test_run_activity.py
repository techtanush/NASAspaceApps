"""Durable activity replay is bounded, workspace/run scoped, and independent of browser history."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.application.activity import page
from analogforge.db.store import Store
from analogforge.main import create_app
from analogforge.ports.domain_models import RunEvent
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import ScienceComputationResult
from analogforge.ports.science_payloads import ResolveCoverageInput, ResolveCoveragePayload
from analogforge.settings import Settings
from tests.integration.platform.test_migrations import platform_store, seed_run
from tests.integration.platform.test_runtime_journey import runtime

__all__ = ["platform_store", "runtime"]


@pytest.mark.db
def test_actual_scheduler_start_is_committed_and_readable_while_the_operation_executes(runtime, monkeypatch) -> None:
    from analogforge.jobs import cpu

    engine, store, workspace, make = runtime
    run = make("synthetic-graph-regression-v1")
    run = engine.advance(run["id"], workspace)
    with store.transaction(workspace) as unit:
        mission = unit.require("mission_revisions", run["mission_revision_id"])

    def execute(_service, request, _context, **_kwargs):
        # page() opens a separate transaction: a browser can see this start before
        # any result/receipt exists, without relying on worker-local memory.
        observed = page(store, workspace, run["id"])
        start = observed["items"][-1]
        assert start["event_type"] == "tool.started" and start["status"] == "RUNNING"
        with store.transaction(workspace) as unit:
            assert unit.require("invocations", start["invocation_id"])["status"] == "RUNNING"
            assert unit.list("tool_receipts", {"run_id": run["id"]}) == []
        return ScienceComputationResult(
            request_id=request.request_id,
            operation=request.operation,
            mode=request.mode,
            status="SUCCEEDED",
            algorithm_id="activity-test",
            algorithm_version="1",
            parameters_sha256="0" * 64,
            input_sha256=canonical_sha256(request),
            payload=ResolveCoveragePayload(selections=[]),
        )

    monkeypatch.setattr(cpu, "run_science", execute)
    engine._compute(
        ResolveCoverageInput(
            subject_kind="TARGET", aoi=mission["target"], adapter_id="synthetic_practice", measurement_kinds=["terrain"]
        ),
        run["id"],
        workspace,
    )
    reloaded = page(store, workspace, run["id"])
    assert [item["status"] for item in reloaded["items"][-2:]] == ["RUNNING", "COMPLETED"]
    assert reloaded["items"][-1]["tool_receipt_id"] is not None


@pytest.mark.db
def test_durable_activity_preserves_sequence_across_reload_append_and_completion(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        invocation = unit.create(
            "invocations",
            {
                "run_id": run["id"],
                "mode": "synthetic",
                "preparation_id": None,
                "role": "scientific_worker",
                "task_kind": "RESOLVE_COVERAGE",
                "status": "RUNNING",
            },
        )
        start = unit.append_event(
            run["id"],
            "tool.started",
            {
                "operation": "RESOLVE_COVERAGE",
                "invocation_id": invocation["id"],
            },
            "synthetic",
        )
    first = page(platform_store, workspace, run["id"], limit=1)
    assert first["items"][0]["status"] == "RUNNING"
    assert first["items"][0]["created_at"] == start["created_at"]
    with platform_store.transaction(workspace) as unit:
        receipt = unit.create(
            "tool_receipts",
            {
                "run_id": run["id"],
                "mode": "synthetic",
                "invocation_id": invocation["id"],
                "tool_name": "resolve_dataset_coverage",
                "status": "BLOCKED",
                "evidence_ids": [],
            },
        )
        unit.append_event(
            run["id"],
            "tool.completed",
            {
                "operation": "RESOLVE_COVERAGE",
                "invocation_id": invocation["id"],
                "receipt_id": receipt["id"],
                "status": "BLOCKED",
            },
            "synthetic",
        )
        current = unit.require("runs", run["id"])
        unit.replace("runs", run["id"], {**current, "state": "BLOCKED"}, current["revision"])
        unit.append_event(run["id"], "run.blocked", {"code": "SOURCE_UNAVAILABLE"}, "synthetic")
    loaded = page(platform_store, workspace, run["id"], limit=1)
    assert loaded["items"] == first["items"]
    assert loaded["next_cursor"] is not None and loaded["last_event_seq"] == 3
    second = page(platform_store, workspace, run["id"], limit=1, cursor=loaded["next_cursor"])
    third = page(platform_store, workspace, run["id"], limit=1, cursor=second["next_cursor"])
    assert [item["seq"] for result in (loaded, second, third) for item in result["items"]] == [1, 2, 3]
    assert second["items"][0]["status"] == third["items"][0]["status"] == "BLOCKED"
    assert second["items"][0]["tool_receipt_id"] == receipt["id"]
    assert third["next_cursor"] is None
    assert all(RunEvent.model_validate(event) for event in platform_store.events(workspace, run["id"]))


@pytest.mark.db
def test_activity_endpoint_rejects_cross_workspace_cursors_and_cross_run_references(
    platform_store: Store,
    tmp_path: Path,
) -> None:
    workspace, run = seed_run(platform_store)
    _, other_run = seed_run(platform_store, workspace)
    foreign, _ = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        invocation = unit.create(
            "invocations",
            {
                "run_id": other_run["id"],
                "mode": "synthetic",
                "preparation_id": None,
                "role": "earth_scout",
                "task_kind": "screen_candidates",
                "status": "SUCCEEDED",
            },
        )
        unit.append_event(
            run["id"],
            "agent.started",
            {
                "role": "requirements",
                "task_kind": "validate_accepted_contract",
                "invocation_id": invocation["id"],
                "summary": "PRIVATE_PROMPT_SENTINEL",
                "reasoning": "PRIVATE_REASONING_SENTINEL",
                "api_key": "sk-private-sentinel",
            },
            "synthetic",
        )
        unit.append_event(run["id"], "run.failed", {"summary": "PRIVATE_EXCEPTION_SENTINEL"}, "synthetic")
    actor = {"workspace": workspace}
    app = create_app(
        settings=Settings(_env_file=None, data_root=tmp_path),
        store=platform_store,
        identity_provider=lambda _request: Principal(actor["workspace"], str(uuid4()), "VIEWER"),
    )
    url = f"/api/v1/runs/{run['id']}/activity"
    with TestClient(app) as client:
        response = client.get(url, params={"limit": 1})
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json()["items"][0]["invocation_id"] is None
        assert "PRIVATE_" not in response.text and "sk-private" not in response.text
        cursor = response.json()["next_cursor"]
        assert client.get(f"/api/v1/runs/{other_run['id']}/activity", params={"cursor": cursor}).status_code == 422
        actor["workspace"] = foreign
        assert client.get(url).status_code == 404
        assert client.get(url, params={"cursor": cursor}).status_code == 422
        actor["workspace"] = workspace
        assert client.get(url, params={"cursor": cursor}).json()["items"][0]["status"] == "FAILED"
