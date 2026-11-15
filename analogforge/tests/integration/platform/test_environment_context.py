"""Actual PostgreSQL lease and private snapshot authorization with mocked provider HTTP."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.application import environment
from analogforge.db.store import LeaseLost, NotFound, Store
from analogforge.main import create_app
from tests.integration.platform.test_migrations import platform_store
from tests.unit.platform.test_environment_context import NOW, network, settings

__all__ = ["platform_store"]


@pytest.mark.db
def test_worker_context_is_fenced_durable_private_and_get_is_stored_only(platform_store: Store, tmp_path, monkeypatch):
    store = platform_store
    workspace = str(uuid4())
    store.ensure_workspace(workspace)
    with store.transaction(workspace) as tx:
        mission = tx.create("missions", {"name": "Environment seam"})
        revision = tx.create("mission_revisions", {"mission_id": mission["id"], "revision": 1,
            "content_sha256": "a" * 64, "target": {"body": "MARS", "bbox": [1, 1, 2, 2]}})
        run = tx.create("runs", {"mission_revision_id": revision["id"], "rover_revision_id": None,
            "mode": "live", "state": "DISCOVERING", "config_sha256": "b" * 64, "runtime": {}})
        candidate = tx.create("candidates", {"run_id": run["id"], "mode": "live", "name": "Context candidate",
            "origin": "USER_SUPPLIED", "aoi": {"body": "EARTH", "bbox": [-112, 35, -111, 36],
                "longitude_convention": "NEG180_180", "latitude_type": "GEODETIC"}})
        run["candidate_ids"] = [candidate["id"]]
        tx.replace("runs", run["id"], run, run["revision"])
        queued = tx.enqueue("ADVANCE_RUN", {"run_id": run["id"]}, run_id=run["id"])
    job = store.claim_job(workspace_id=workspace)
    assert job["id"] == queued["id"]
    configured = settings(tmp_path)
    actor = {"workspace": workspace}
    app = create_app(settings=configured, store=store,
                     identity_provider=lambda request: Principal(actor["workspace"], str(uuid4()), "VIEWER"))
    blobs = app.state.runtime.blobs
    requests, factory = network(monkeypatch)
    environment.capture(store, blobs, configured, workspace, run["id"], job_id=job["id"],
                        lease_token=job["lease_token"], client_factory=factory, now=lambda: NOW)
    snapshot = environment.project(store, blobs, configured, workspace, run["id"])
    assert snapshot["earth_candidates"][0]["candidate_id"] == candidate["id"]
    assert len(requests) == 3 and snapshot["nasa_reference"]["status"] == "LIMITED"
    with store.transaction(workspace) as tx:
        assert tx.list("evidence", {"run_id": run["id"]}) == []  # Context creates no scientific claims.
        assert tx.list("artifacts", {"sha256": snapshot["snapshot_sha256"]}) == []
        assert tx.require("runs", run["id"])["runtime"][environment.KEY]["sha256"] == snapshot["snapshot_sha256"]
    before = len(requests)
    with TestClient(app) as client:
        url = f"/api/v1/runs/{run['id']}/environment"
        response = client.get(url)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json()["snapshot_sha256"] == snapshot["snapshot_sha256"]
        assert client.get(f"/api/v1/artifacts/{snapshot['snapshot_sha256']}").status_code == 404
        actor["workspace"] = str(uuid4())
        assert client.get(url).status_code == 404
    assert len(requests) == before
    with pytest.raises(NotFound):
        environment.project(store, blobs, configured, str(uuid4()), run["id"])
    with pytest.raises(LeaseLost):
        environment.capture(store, blobs, configured, workspace, run["id"], job_id=job["id"],
                            lease_token=str(uuid4()), client_factory=factory)
