"""Exercise the real HTTP boundary, not just the document returned by openapi()."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.contracts import specification, validate
from analogforge.api.dependencies import Principal
from analogforge.api.router import build_router
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.main import create_app
from analogforge.settings import Settings

APP = Path(__file__).resolve().parents[3]


@pytest.fixture
def harness(tmp_path: Path) -> tuple[TestClient, Store, Principal]:
    configured = Settings()
    assert configured.test_database_url, "TEST_DATABASE_URL must name an isolated PostgreSQL/PostGIS database"
    store = Store(configured.test_database_url)
    store.migrate()
    settings = Settings(
        _env_file=None,
        database_url=configured.test_database_url,
        data_root=tmp_path / "data",
        config_dir=APP / "config",
    )
    seed_synthetic(store, settings)
    principal = Principal(str(uuid4()), str(uuid4()))
    store.ensure_workspace(principal.workspace_id)
    with store.transaction(principal.workspace_id) as unit:
        unit.create("users", {"id": principal.subject_id, "issuer": "test", "subject": principal.subject_id})
    app = create_app(settings=settings, store=store, identity_provider=lambda request: principal)
    with TestClient(app) as client:
        yield client, store, principal
    store.close()


def body(name: str = "Terrain investigation") -> dict[str, Any]:
    return {
        "name": name,
        "objective": "Determine support for an engineering terrain test.",
        "target": {
            "body": "MARS",
            "bbox": [137, -5, 138, -4],
            "longitude_convention": "ZERO_360",
            "latitude_type": "PLANETOCENTRIC",
            "crs_wkt": None,
            "vertical_datum": "Mars areoid",
        },
    }


def post(client: TestClient, path: str, value: dict[str, Any], key: str | None = None) -> Any:
    return client.post("/api/v1" + path, json=value, headers={"Idempotency-Key": key or str(uuid4())})


def assert_contract(response: Any, method: str, path: str) -> None:
    operation = specification()["paths"][path][method]
    assert str(response.status_code) in operation["responses"], (path, response.status_code, response.text)
    schema = (
        operation["responses"][str(response.status_code)].get("content", {}).get("application/json", {}).get("schema")
    )
    if schema:
        validate(response.json(), schema)


def test_all_43_registered_operations_match_frozen_contract() -> None:
    expected = {
        (path, method.upper(), op["operationId"])
        for path, methods in specification()["paths"].items()
        for method, op in methods.items()
        if method in {"get", "post"}
    }
    actual = {
        (route.path.removeprefix("/api/v1"), next(iter(route.methods)), route.operation_id)
        for route in build_router().routes
    }
    assert len(actual) == 43
    assert actual == expected


def test_mission_draft_revision_acceptance_and_immutable_history(harness: Any) -> None:
    client, store, principal = harness
    created = post(client, "/missions", body())
    assert_contract(created, "post", "/missions")
    mission = created.json()
    initial_draft_id = mission["current_draft_id"]
    changed = post(
        client,
        f"/missions/{mission['id']}/drafts",
        {"expected_revision": mission["revision"], "draft": body("Changed intent")},
    )
    assert_contract(changed, "post", "/missions/{id}/drafts")
    assert client.get(f"/api/v1/mission-drafts/{initial_draft_id}").json()["draft"]["name"] == body()["name"]
    header = client.get(f"/api/v1/missions/{mission['id']}")
    assert_contract(header, "get", "/missions/{id}")
    contract = json.loads((APP / "tests/fixtures/kit/missions/mission-mars-mobility.json").read_text())
    content = {
        key: contract[key]
        for key in ["name", "objective", "target", "requirements", "assumptions", "forbidden_actions"]
    }
    revision = post(
        client,
        f"/missions/{mission['id']}/revisions",
        {"expected_revision": header.json()["revision"], "contract": content},
    )
    assert_contract(revision, "post", "/missions/{id}/revisions")
    header = client.get(f"/api/v1/missions/{mission['id']}").json()
    accepted = post(
        client,
        f"/missions/{mission['id']}/accept",
        {"expected_revision": header["revision"], "revision_id": revision.json()["id"]},
    )
    assert_contract(accepted, "post", "/missions/{id}/accept")
    assert accepted.json()["accepted_at"] is not None
    assert accepted.json()["content_sha256"] == revision.json()["content_sha256"]
    historical = client.get(f"/api/v1/mission-revisions/{revision.json()['id']}")
    assert_contract(historical, "get", "/mission-revisions/{id}")
    assert historical.json() == accepted.json()
    with store.transaction(principal.workspace_id) as unit:
        assert unit.require("mission_revisions", revision.json()["id"])["accepted_at"] is None
        assert len(unit.list("mission_acceptances", {"mission_revision_id": revision.json()["id"]})) == 1


def test_rover_import_revision_and_original_remain_separate(harness: Any) -> None:
    client, _, _ = harness
    profile = json.loads((APP / "tests/fixtures/kit/rovers/ares-1.json").read_text())
    created = post(client, "/rovers", profile)
    assert_contract(created, "post", "/rovers")
    assert created.status_code == 201, created.text
    rover = created.json()
    update = post(
        client,
        f"/rovers/{rover['rover_id']}/revisions",
        {"expected_revision": 1, "profile": {**profile, "name": "Revised rover"}},
    )
    assert_contract(update, "post", "/rovers/{id}/revisions")
    assert update.json()["id"] != rover["id"]
    assert client.get(f"/api/v1/rover-revisions/{rover['id']}").json() == rover
    assert client.get(f"/api/v1/rovers/{rover['rover_id']}").json() == update.json()
    assert_contract(client.get("/api/v1/rovers"), "get", "/rovers")


@pytest.mark.parametrize("path", ["/health/live", "/health/ready", "/capabilities"])
def test_healthy_reads_validate_and_never_expose_configuration_secrets(harness: Any, path: str) -> None:
    client, _, _ = harness
    response = client.get("/api/v1" + path)
    assert_contract(response, "get", path)
    assert response.status_code == 200
    assert "DATABASE_URL" not in response.text and "OPENAI_API_KEY" not in response.text


def test_all_scenarios_and_list_cursors(harness: Any) -> None:
    client, _, _ = harness
    capabilities = client.get("/api/v1/capabilities").json()
    assert len(capabilities["scenario_config_ids"]) == 5
    for scenario_id in capabilities["scenario_config_ids"]:
        response = client.get(f"/api/v1/configuration/scenarios/{scenario_id}")
        assert_contract(response, "get", "/configuration/scenarios/{id}")
        assert response.json()["id"] == scenario_id
    for name in ["First", "Second", "Third"]:
        assert post(client, "/missions", body(name)).status_code == 201
    first = client.get("/api/v1/missions?limit=2")
    assert_contract(first, "get", "/missions")
    second = client.get("/api/v1/missions", params={"limit": 2, "cursor": first.json()["next_cursor"]})
    assert len(second.json()["items"]) == 1
    assert {row["id"] for row in first.json()["items"]}.isdisjoint({row["id"] for row in second.json()["items"]})
    assert client.get("/api/v1/missions?limit=101").status_code == 422
    assert client.get("/api/v1/missions?cursor=invalid").status_code == 422


def test_idempotency_body_collision_and_stale_parent_have_no_side_effect(harness: Any) -> None:
    client, _, _ = harness
    key = str(uuid4())
    first = post(client, "/missions", body(), key)
    repeated = post(client, "/missions", body(), key)
    assert first.status_code == repeated.status_code == 201 and first.json() == repeated.json()
    collision = post(client, "/missions", body("Different body"), key)
    assert collision.status_code == 409 and collision.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    mission_id = first.json()["id"]
    assert (
        post(client, f"/missions/{mission_id}/drafts", {"expected_revision": 1, "draft": body("Next")}).status_code
        == 201
    )
    stale = post(client, f"/missions/{mission_id}/drafts", {"expected_revision": 1, "draft": body("Stale")})
    assert stale.status_code == 409
    assert client.get(f"/api/v1/missions/{mission_id}").json()["name"] == "Next"


def test_foreign_workspace_enumeration_and_unknown_records_are_404(harness: Any) -> None:
    client, store, principal = harness
    other = str(uuid4())
    store.ensure_workspace(other)
    with store.transaction(other) as unit:
        from analogforge.application.missions import create

        mission = create(unit, other, body("Secret other mission"))
    response = client.get(f"/api/v1/missions/{mission['id']}")
    assert response.status_code == 404
    assert "Secret other mission" not in client.get("/api/v1/missions").text
    for path in [
        "runs",
        "mission-drafts",
        "mission-revisions",
        "rover-revisions",
        "candidates",
        "qualifications",
        "tests",
        "test-results",
        "portfolios",
        "evidence",
        "passports",
        "target-profiles",
        "tool-receipts",
        "reviews",
        "jobs",
    ]:
        assert client.get(f"/api/v1/{path}/{uuid4()}").status_code == 404, path
    assert principal.workspace_id != other


@pytest.mark.parametrize(
    "mutation",
    [
        {"extra": True},
        {
            "target": {
                "body": "MARS",
                "bbox": [137, 91, 138, 92],
                "longitude_convention": "ZERO_360",
                "latitude_type": "PLANETOCENTRIC",
                "crs_wkt": None,
                "vertical_datum": "Mars",
            }
        },
    ],
)
def test_structural_and_semantic_bad_inputs_are_rejected(harness: Any, mutation: dict[str, Any]) -> None:
    client, _, _ = harness
    response = post(client, "/missions", {**body(), **mutation})
    assert response.status_code == 422
    assert_contract(response, "post", "/missions")
    assert client.get("/api/v1/missions").json()["items"] == []
