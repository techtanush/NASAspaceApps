"""HTTP projections expose real registered science without publishing or mutating anything."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.api.visualization_contracts import validate_response
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.integration.platform.test_runtime_journey import advance_until
from tests.integration.platform.test_runtime_journey import runtime as runtime


def _client(engine: Any, store: Any, ws: str) -> TestClient:
    configured = Settings(
        _env_file=None,
        database_url=Settings().test_database_url,
        data_root=engine.settings.data_root,
        config_dir=engine.settings.config_dir,
        visualization_enabled=True,
    )
    app = create_app(settings=configured, store=store, identity_provider=lambda request: Principal(ws, str(uuid4())))
    # The standalone scheduler fixture owns a CAS under data_root/blobs. Production
    # passes one shared CAS into scheduler and HTTP, so preserve that same seam here.
    app.state.runtime.blobs = engine.blobs
    return TestClient(app)


def _counts(store: Any, ws: str, run_id: str) -> dict[str, Any]:
    with store.transaction(ws) as uow:
        return {
            "run": uow.require("runs", run_id),
            "counts": {
                kind: len(uow.list(kind, {"run_id": run_id}))
                for kind in ["jobs", "tool_receipts", "evidence", "display_layers", "test_results"]
            },
        }


def test_readonly_http_projection_of_real_registered_science(runtime: Any) -> None:
    engine, store, ws, make = runtime
    run = advance_until(engine, make(no_rover=True), ws, {"AWAITING_REVIEW", "COMPLETED", "BLOCKED", "FAILED"})
    assert run["state"] in {"AWAITING_REVIEW", "COMPLETED"}
    assert run["candidate_ids"]
    before = _counts(store, ws, run["run_id"])
    measured = 0
    with _client(engine, store, ws) as client:
        target = client.get(f"/api/v1/runs/{run['run_id']}/visualization/target")
        assert target.status_code == 200, target.text
        validate_response(target.json(), "VizSiteDetailV1")
        assert target.json()["body"] == "MARS"
        assert target.json()["availability"] == "AVAILABLE"
        for candidate_id in run["candidate_ids"]:
            path = f"/api/v1/runs/{run['run_id']}/visualization/candidates/{candidate_id}"
            detail = client.get(path)
            assert detail.status_code == 200, detail.text
            validate_response(detail.json(), "VizSiteDetailV1")
            assert detail.json()["candidate_id"] == candidate_id
            assert detail.json()["availability"] == "AVAILABLE"
            assert detail.json()["body"] == "EARTH"
            benchmarks = client.get(path + "/benchmarks")
            assert benchmarks.status_code == 200, benchmarks.text
            validate_response(benchmarks.json(), "VizSiteBenchmarksV1")
            assert benchmarks.json()["candidate_id"] == candidate_id
            for row in benchmarks.json()["requirements"]:
                value = row["measurement"]["value"]
                if value is not None:
                    measured += 1
                    assert row["measurement"]["comparison_evidence_id"]
                    assert row["measurement"]["receipt_id"]
                    assert row["measurement"]["unit"] == row["requirement"]["unit"]
            assert benchmarks.json()["test_result_ids"] == []  # no rover, no borrowed route results
        assert measured > 0
        unpinned = client.get(f"/api/v1/runs/{run['run_id']}/visualization/candidates/{uuid4()}")
        assert unpinned.status_code == 404
    assert _counts(store, ws, run["run_id"]) == before
    foreign = str(uuid4())
    store.ensure_workspace(foreign)
    with _client(engine, store, foreign) as client:
        for suffix in [
            "target",
            f"candidates/{run['candidate_ids'][0]}",
            f"candidates/{run['candidate_ids'][0]}/benchmarks",
        ]:
            r = client.get(f"/api/v1/runs/{run['run_id']}/visualization/{suffix}")
            assert r.status_code == 404
            assert run["mission_revision_id"] not in r.text


def test_target_not_yet_characterized_is_unavailable_without_starting_work(runtime: Any) -> None:
    engine, store, ws, make = runtime
    run = make(no_rover=True)
    before = _counts(store, ws, run["run_id"])
    with _client(engine, store, ws) as client:
        r = client.get(f"/api/v1/runs/{run['run_id']}/visualization/target")
        assert r.status_code == 200, r.text
        assert r.json()["availability"] == "UNAVAILABLE"
        assert r.json()["display_layer_manifest_ids"] == []
    assert _counts(store, ws, run["run_id"]) == before
