"""Optional weather capture and stored-only reads preserve scope, mode and lease boundaries."""

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.api.errors import ApiError
from analogforge.application import environment
from analogforge.db.store import LeaseLost, NotFound, PersistenceError
from analogforge.ports.hashing import canonical_json_bytes
from analogforge.settings import Settings

NOW = datetime(2026, 11, 14, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "real" / "rems"
NAME = "RME_397535244RMD00010000000_______PA"


class EnvironmentStore:
    def __init__(self, count=1):
        self.workspace, self.run, self.mission, self.job, self.token = (str(uuid4()) for _ in range(5))
        self.valid_lease = True
        self.rows = {
            "runs": {self.run: {"id": self.run, "workspace_id": self.workspace, "mode": "live", "revision": 1,
                                "state": "DISCOVERING", "mission_revision_id": self.mission, "runtime": {}}},
            "mission_revisions": {self.mission: {"id": self.mission, "workspace_id": self.workspace,
                "content_sha256": "1" * 64, "target": {"body": "MARS", "bbox": [1, 1, 2, 2]}}},
            "jobs": {self.job: {"id": self.job, "workspace_id": self.workspace, "run_id": self.run}},
            "candidates": {},
        }
        for i in range(count):
            cid = str(uuid4())
            self.rows["candidates"][cid] = {"id": cid, "workspace_id": self.workspace, "run_id": self.run,
                "mode": "live", "aoi": {"body": "EARTH", "bbox": [-112 + i, 35, -111 + i, 36],
                                           "longitude_convention": "NEG180_180", "latitude_type": "GEODETIC"}}
        self.rows["runs"][self.run]["candidate_ids"] = list(self.rows["candidates"])

    @contextmanager
    def transaction(self, workspace):
        def require(kind, identifier, **kwargs):
            record = self.rows.get(kind, {}).get(identifier)
            if not record or record["workspace_id"] != workspace:
                raise NotFound()
            return deepcopy(record)

        def rows(kind, filters):
            return [deepcopy(row) for row in self.rows.get(kind, {}).values()
                    if row["workspace_id"] == workspace and all(row.get(k) == v for k, v in filters.items())]

        def replace(kind, identifier, record, revision=None):
            assert record["workspace_id"] == workspace
            assert revision is None or revision == self.rows[kind][identifier]["revision"]
            self.rows[kind][identifier] = deepcopy(record)
            self.rows[kind][identifier]["revision"] += 1
        yield SimpleNamespace(require=require, list=rows, replace=replace)

    @contextmanager
    def publication(self, workspace, job, token):
        if not self.valid_lease or token != self.token or job != self.job:
            raise LeaseLost()
        if self.rows["runs"][self.run]["state"] == "CANCELLED":
            raise PersistenceError("RUN_CANCELLED", "Cancelled")
        with self.transaction(workspace) as tx:
            yield tx
        if not self.valid_lease:
            raise LeaseLost()


def settings(tmp_path, **changes):
    return Settings(_env_file=None, data_root=tmp_path, environment_context_enabled=True,
                    meteomatics_username="dummy-account", meteomatics_password="dummy-secret", **changes)  # noqa: S106


def network(monkeypatch, *, on_request=None, status=200):
    requests = []
    real_rems = environment.fetch_rems_weather
    monkeypatch.setattr(environment, "fetch_rems_weather", lambda **kwargs: real_rems(sol=1, **kwargs))

    def respond(request):
        requests.append(request)
        if on_request:
            on_request(request)
        if request.url.host == "pds-atmospheres.nmsu.edu":
            assert "authorization" not in request.headers
            suffix = ".xml" if request.url.path.endswith(".xml") else ".TAB"
            return httpx.Response(200, content=(FIXTURES / (NAME + suffix)).read_bytes())
        if status != 200:
            return httpx.Response(status, text="user=dummy-account password=dummy-secret private-provider-error")
        path = request.url.path.strip("/").split("/")
        start = datetime.fromisoformat(path[0].split("--")[0].replace("Z", "+00:00"))
        latitude, longitude = map(float, path[2].split(","))
        data = [{"parameter": parameter, "coordinates": [{"lat": latitude, "lon": longitude, "dates": [
            {"date": (start + timedelta(hours=i)).isoformat(), "value": 10.0} for i in range(4)]}]}
            for parameter in path[1].split(",")]
        return httpx.Response(200, json={"status": "OK", "dateGenerated": NOW.isoformat(),
                                        "user": "dummy-account", "data": data})
    return requests, lambda **kwargs: httpx.Client(transport=httpx.MockTransport(respond), **kwargs)


def capture(store, blobs, configured, factory, **changes):
    environment.capture(store, blobs, configured, store.workspace, store.run,
                        job_id=store.job, lease_token=store.token, client_factory=factory, now=lambda: NOW, **changes)


def test_capture_once_uses_actual_candidate_points_bounded_calls_and_original_nasa_quality(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(8), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    requests, factory = network(monkeypatch)
    capture(store, blobs, configured, factory)
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["status"] == "CAPTURED" and len(result["earth_candidates"]) == 6
    assert len(requests) == result["budget"]["http_calls"] == 8 and len(result["omitted_candidate_ids"]) == 2
    for item in result["earth_candidates"]:
        aoi = store.rows["candidates"][item["candidate_id"]]["aoi"]
        assert item["representative_point"]["latitude"] == 35.5
        assert item["representative_point"]["longitude"] == (aoi["bbox"][0] + aoi["bbox"][2]) / 2
        assert item["weather"]["query"]["body"] == "EARTH"
    assert result["nasa_reference"]["status"] == "LIMITED"
    assert result["nasa_reference"]["selected_aoi_applicability"] == "UNKNOWN"
    assert result["nasa_reference"]["geographic_coordinates"] is None
    assert result["operating_limits"] == [] and result["qualification_supported"] is False
    raw = blobs.read(result["snapshot_sha256"]).decode()
    assert not any(value in raw for value in ("dummy-account", "dummy-secret", "private-provider-error"))
    pointer = deepcopy(store.rows["runs"][store.run]["runtime"][environment.KEY])
    capture(store, blobs, configured, factory)
    assert len(requests) == 8 and store.rows["runs"][store.run]["runtime"][environment.KEY] == pointer


@pytest.mark.parametrize("mode,change,reason", [
    ("synthetic", {}, "NETWORK_DISABLED_FOR_MODE"), ("replay", {}, "NETWORK_DISABLED_FOR_MODE"),
    ("live", {"environment_context_enabled": False}, "ENVIRONMENT_CONTEXT_DISABLED"),
    ("live", {"meteomatics_password": None}, "WEATHER_NOT_CONFIGURED"),
    ("live", {"test_hooks": True}, "NETWORK_DISABLED_FOR_TEST_MODE"),
])
def test_default_off_modes_missing_credentials_and_test_hooks_never_network(tmp_path, mode, change, reason):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store = EnvironmentStore()
    store.rows["runs"][store.run]["mode"] = mode
    configured = settings(tmp_path).model_copy(update=change)
    blobs = ContentAddressedStore(tmp_path)
    def forbidden(**kwargs):
        pytest.fail("Network factory must not be reached")
    capture(store, blobs, configured, forbidden)
    assert environment.ATTEMPT not in store.rows["runs"][store.run]["runtime"]
    assert environment.project(store, blobs, configured, store.workspace, store.run)["reason_code"] == reason
    assert Settings(_env_file=None).environment_context_enabled is False
    assert "meteomatics_password" not in configured.public_config()
    assert "meteomatics_username" not in configured.public_config()


@pytest.mark.parametrize("kind", ["cancel", "lease"])
def test_cancelled_or_lost_lease_cannot_publish_late_context(tmp_path, monkeypatch, kind):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    def interrupt(request):
        if kind == "lease":
            store.valid_lease = False
        else:
            store.rows["runs"][store.run]["state"] = "CANCELLED"
    _, factory = network(monkeypatch, on_request=interrupt)
    with pytest.raises((LeaseLost, PersistenceError)):
        capture(store, blobs, configured, factory)
    assert environment.KEY not in store.rows["runs"][store.run]["runtime"]


def test_budget_covers_provider_parsing_and_prevents_retries(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    clock = [0.0]
    requests, factory = network(monkeypatch, on_request=lambda request: clock.__setitem__(0, 31.0))
    capture(store, blobs, configured, factory, monotonic=lambda: clock[0])
    assert len(requests) == 1 and environment.KEY not in store.rows["runs"][store.run]["runtime"]
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["reason_code"] == "CONTEXT_BUDGET_EXHAUSTED"
    capture(store, blobs, configured, factory)
    assert len(requests) == 1


def test_checksum_and_storage_time_are_inside_capture_budget(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    clock = [0.0]
    original_put = blobs.put_bytes
    def delayed_checksum(*args, **kwargs):
        blob = original_put(*args, **kwargs)
        clock[0] = 31.0
        return blob
    monkeypatch.setattr(blobs, "put_bytes", delayed_checksum)
    _, factory = network(monkeypatch)
    capture(store, blobs, configured, factory, monotonic=lambda: clock[0])
    assert environment.KEY not in store.rows["runs"][store.run]["runtime"]
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["reason_code"] == "CONTEXT_BUDGET_EXHAUSTED"


def test_live_capture_without_worker_job_and_lease_never_reaches_providers(tmp_path):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    def forbidden(**kwargs):
        pytest.fail("Only a leased worker may capture context")
    environment.capture(store, ContentAddressedStore(tmp_path), configured, store.workspace, store.run,
                        job_id=None, lease_token=None, client_factory=forbidden)
    assert store.rows["runs"][store.run]["runtime"] == {}


@pytest.mark.parametrize("defect", ["mode", "run", "missing"])
def test_capture_rejects_invalid_authoritative_candidate_scope_without_network(tmp_path, defect):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    candidate = next(iter(store.rows["candidates"].values()))
    if defect == "missing":
        store.rows["runs"][store.run]["candidate_ids"] = [str(uuid4())]
    else:
        candidate["mode" if defect == "mode" else "run_id"] = "synthetic" if defect == "mode" else str(uuid4())
    def forbidden(**kwargs):
        pytest.fail("Invalid candidate scope must not reach providers")
    blobs = ContentAddressedStore(tmp_path)
    capture(store, blobs, configured, forbidden)
    assert environment.KEY not in store.rows["runs"][store.run]["runtime"]
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["reason_code"] == "CANDIDATE_SCOPE_INVALID"


def test_capture_ignores_orphan_candidate_rows_outside_authoritative_shortlist(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(2), settings(tmp_path)
    authoritative, orphan = list(store.rows["candidates"])
    store.rows["runs"][store.run]["candidate_ids"] = [authoritative]
    blobs = ContentAddressedStore(tmp_path)
    _, factory = network(monkeypatch)
    capture(store, blobs, configured, factory)
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert list(result["candidate_aoi_sha256"]) == [authoritative]
    assert orphan not in result["omitted_candidate_ids"]


def test_candidate_scope_change_during_capture_is_nonfatal_and_cannot_publish(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    candidate = next(iter(store.rows["candidates"].values()))
    _, factory = network(monkeypatch, on_request=lambda request: candidate.update(mode="synthetic"))
    blobs = ContentAddressedStore(tmp_path)
    capture(store, blobs, configured, factory)
    assert environment.KEY not in store.rows["runs"][store.run]["runtime"]
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["reason_code"] == "CONTEXT_INPUTS_CHANGED"


@pytest.mark.parametrize("defect", ["mode", "membership"])
def test_stored_projection_rejects_changed_authoritative_candidate_binding(tmp_path, monkeypatch, defect):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    _, factory = network(monkeypatch)
    capture(store, blobs, configured, factory)
    if defect == "membership":
        store.rows["runs"][store.run]["candidate_ids"] = []
    else:
        next(iter(store.rows["candidates"].values()))["mode"] = "synthetic"
    with pytest.raises(ApiError, match="could not be verified"):
        environment.project(store, blobs, configured, store.workspace, store.run)


def test_discovery_checkpoint_captures_after_candidates_and_preserves_pointer_in_next_state(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    from analogforge.application.scheduler import WorkflowEngine
    store, configured = EnvironmentStore(), settings(tmp_path)
    ids = list(store.rows["candidates"])
    store.rows["runs"][store.run].update(candidate_ids=ids, scenario_config_id="test")
    for candidate in store.rows["candidates"].values():
        candidate.update(window_id="existing-window", name="Existing candidate", origin="USER_SUPPLIED",
                         novelty_status="NOT_ASSESSED", discovery_method="user-nominated-aoi")
        candidate["aoi"].update(crs_wkt=None, vertical_datum="EGM96")
    store.rows["target_profiles"] = {"target": {"metrics": [], "payload": {"slope_histogram": None}}}
    _, factory = network(monkeypatch)
    original_capture = environment.capture
    def bounded_capture(*args, **kwargs):
        assert ids == list(store.rows["candidates"])
        return original_capture(*args, **kwargs, client_factory=factory, now=lambda: NOW)
    monkeypatch.setattr(environment, "capture", bounded_capture)
    engine = object.__new__(WorkflowEngine)
    engine.store, engine.settings, engine.blobs = store, configured, ContentAddressedStore(tmp_path)
    engine._scenario = MagicMock(return_value={
        "earth_source": {"kind": "SYNTHETIC_FIXTURE", "fixture_id": "isolated-science-seam"},
        "search_region_set_id": "test", "reference_set_id": "test", "operator_limits": {},
    })
    engine._rows = MagicMock(side_effect=lambda workspace, table, run: list(store.rows[table].values()))
    engine._compute = MagicMock(return_value=SimpleNamespace(payload={}, receipt={"id": str(uuid4())}, evidence_ids=[]))
    engine._role = MagicMock()  # No model or scientific computation is called by this seam fixture.
    engine._load = MagicMock(side_effect=lambda *args: (deepcopy(store.rows["runs"][store.run]), {}, None))
    engine._save_run = MagicMock(return_value={"state": "QUALIFYING"})
    # The existing scheduler accepts the wire RunSnapshot, while capture uses persisted run.id.
    wire_run = {**store.rows["runs"][store.run], "run_id": store.run}
    engine._advance_step(wire_run, {"requirements": []}, None, store.workspace, store.job, store.token)
    saved_changes = engine._save_run.call_args.args[2]
    assert saved_changes["state"] == "QUALIFYING"
    assert saved_changes["runtime"][environment.KEY]["sha256"]
    assert engine._compute.call_count == 2


def test_provider_failure_is_nonfatal_unknown_and_get_never_network(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    requests, factory = network(monkeypatch, status=401)
    capture(store, blobs, configured, factory)
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["earth_candidates"][0]["reason_code"] == "WEATHER_AUTH_FAILED"
    before = len(requests)
    environment.project(store, blobs, configured, store.workspace, store.run)
    assert len(requests) == before and "dummy-secret" not in json.dumps(result)


def test_optional_storage_failure_does_not_fail_science_or_publish_a_dangling_pointer(tmp_path, monkeypatch):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    _, factory = network(monkeypatch)
    def unavailable(*args, **kwargs):
        raise OSError("private filesystem exception")
    monkeypatch.setattr(blobs, "put_bytes", unavailable)
    capture(store, blobs, configured, factory)
    assert store.rows["runs"][store.run]["state"] == "DISCOVERING"
    assert environment.KEY not in store.rows["runs"][store.run]["runtime"]
    result = environment.project(store, blobs, configured, store.workspace, store.run)
    assert result["reason_code"] == "CONTEXT_STORAGE_UNAVAILABLE"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("defect", ["run", "workspace", "mode", "target", "candidate"])
def test_snapshot_scope_is_checked_before_private_blob_projection(tmp_path, monkeypatch, defect):
    from analogforge.adapters.storage.cas import ContentAddressedStore
    store, configured = EnvironmentStore(), settings(tmp_path)
    blobs = ContentAddressedStore(tmp_path)
    _, factory = network(monkeypatch)
    capture(store, blobs, configured, factory)
    snapshot = environment.project(store, blobs, configured, store.workspace, store.run)
    snapshot.pop("snapshot_sha256")
    if defect == "run":
        snapshot["run_id"] = str(uuid4())
    elif defect == "workspace":
        snapshot["workspace_id"] = str(uuid4())
    elif defect == "mode":
        snapshot["mode"] = "synthetic"
    elif defect == "target":
        snapshot["target"]["body"] = "MOON"
    else:
        snapshot["candidate_aoi_sha256"] = {str(uuid4()): "0" * 64}
    blob = blobs.put_bytes(canonical_json_bytes(snapshot))
    store.rows["runs"][store.run]["runtime"][environment.KEY]["sha256"] = blob.sha256
    with pytest.raises(ApiError, match="could not be verified"):
        environment.project(store, blobs, configured, store.workspace, store.run)


def test_endpoint_is_authenticated_workspace_scoped_stored_only_no_store_and_not_in_frozen_api(tmp_path):
    from analogforge.main import create_app
    store, configured = EnvironmentStore(), settings(tmp_path)
    app = create_app(settings=configured, store=store,
                     identity_provider=lambda request: Principal(store.workspace, str(uuid4()), "VIEWER"))
    with TestClient(app) as client:
        url = f"/api/v1/runs/{store.run}/environment"
        response = client.get(url)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json()["reason_code"] == "NOT_CAPTURED"
        assert client.get("/api/v1/runs/invalid/environment").status_code == 422
        app.state.identity_provider = lambda request: Principal(str(uuid4()), str(uuid4()), "VIEWER")
        assert client.get(url).status_code == 404
        def unauthenticated(request):
            raise ApiError("UNAUTHENTICATED", "Session required", 401)
        app.state.identity_provider = unauthenticated
        assert client.get(url).status_code == 401
    assert all("environment" not in path for path in app.openapi()["paths"])


def test_earth_dateline_midpoint_and_planetary_coordinate_rejection():
    aoi = {"body": "EARTH", "bbox": [179, 10, -179, 12], "latitude_type": "GEODETIC",
           "longitude_convention": "NEG180_180"}
    assert environment.representative_point(aoi) == (11, -180)
    with pytest.raises(ValueError):
        environment.representative_point({**aoi, "body": "MARS"})
