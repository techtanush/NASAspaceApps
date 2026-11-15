"""The optional API is explicit, documented and compatible with the immutable core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, ValidationError

from analogforge.api.contracts import specification
from analogforge.api.routers.visualization import build_visualization_router
from analogforge.api.visualization_contracts import OPERATIONS, effective_specification, validate_response
from analogforge.main import create_app
from analogforge.settings import Settings

REPO = Path(__file__).resolve().parents[4]


def settings(tmp_path: Path, enabled: bool = True, **extra: Any) -> Settings:
    return Settings(_env_file=None, data_root=tmp_path, visualization_enabled=enabled, **extra)


def client(tmp_path: Path, enabled: bool = True, **extra: Any) -> TestClient:
    return TestClient(create_app(settings=settings(tmp_path, enabled, **extra), store=object()))


def test_extension_preserves_every_core_operation_and_schema() -> None:
    core = specification()
    original = json.loads(json.dumps(core))
    extended = effective_specification()
    for path, definition in core["paths"].items():
        assert extended["paths"][path] == definition
    for name, schema in core["components"]["schemas"].items():
        assert extended["components"]["schemas"][name] == schema
    actual = {(r.path.removeprefix("/api/v1"), r.operation_id) for r in build_visualization_router().routes}
    assert actual == {(path, op) for path, op, _ in OPERATIONS}
    assert all(extended["paths"][path]["get"]["operationId"] == op for path, op, _ in OPERATIONS)
    assert len(extended["paths"]) == len(core["paths"]) + len(OPERATIONS)
    extended["paths"].clear()
    assert specification() == original
    assert effective_specification()["paths"]


@pytest.mark.parametrize("name", ["imagery-catalog", "coverage", "site-detail"])
def test_packaged_schema_equals_the_shared_planning_seam(name: str) -> None:
    packaged = REPO / f"analogforge/src/analogforge/api/visualization_schemas/{name}.v1.schema.json"
    planned = REPO / f"team handoffs/ui-split/schemas/{name}.v1.schema.json"
    assert json.loads(packaged.read_text()) == json.loads(planned.read_text())


def test_flag_is_opt_in_and_does_not_change_scientific_config_hash(tmp_path: Path) -> None:
    disabled, enabled = settings(tmp_path, False), settings(tmp_path, True)
    assert Settings(_env_file=None).visualization_enabled is False
    assert disabled.effective_config_sha256() == enabled.effective_config_sha256()
    off = create_app(settings=disabled, store=object())
    on = create_app(settings=enabled, store=object())
    assert off.openapi() == specification()
    assert on.openapi() == effective_specification()
    with TestClient(off) as c:
        assert c.get("/api/v1/visualization/capabilities").status_code == 404


def test_enabled_capability_and_openapi_are_self_consistent(tmp_path: Path) -> None:
    with client(tmp_path) as c:
        r = c.get("/api/v1/visualization/capabilities")
        assert r.status_code == 200
        validate_response(r.json(), "VizCapabilitiesV1")
        assert r.headers["cache-control"] == "no-store"
        document = c.get(r.json()["openapi_path"])
        assert document.status_code == 200
        assert document.json() == effective_specification()
        assert c.get("/docs").status_code == 404
        assert c.post("/api/v1/visualization/capabilities", json={}).status_code == 405


def test_extension_still_requires_verified_identity_in_oidc(tmp_path: Path) -> None:
    with client(
        tmp_path,
        auth_mode="oidc",
        session_secret="a" * 32,
        oidc_issuer_url="https://issuer.invalid",
        oidc_client_id="unit-client",
        oidc_client_secret="x" * 32,
        public_base_url="https://analogforge.invalid",
    ) as c:
        r = c.get("/api/v1/visualization/capabilities")
        assert r.status_code == 401
        assert "error" in r.json()


@pytest.mark.parametrize(
    "query",
    [
        "",
        "body=MARS&bbox=1,2,3,4",
        "body=MARS&bbox=NaN,2,3,4&scenario_config_id=x",
        "body=MARS&bbox=1,2,3&scenario_config_id=x",
        "body=MARS&bbox=1,2,3,4&scenario_config_id=x&body=MOON",
        "body=MARS&bbox=1,2,3,4&scenario_config_id=x&provider_url=https://example.invalid",
        "body=MARS&bbox=" + "1" * 257 + "&scenario_config_id=x",
    ],
)
def test_malformed_or_ambiguous_coverage_query_fails_without_store(tmp_path: Path, query: str) -> None:
    with client(tmp_path) as c:
        r = c.get("/api/v1/visualization/coverage?" + query)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INPUT_INVALID"


def test_unbound_coverage_is_honest_and_no_provider_or_db_is_needed(tmp_path: Path) -> None:
    with client(tmp_path) as c:
        r = c.get(
            "/api/v1/visualization/coverage",
            params={"body": "MARS", "bbox": "137.25,-4.95,137.55,-4.65", "scenario_config_id": "live-hackathon-v1"},
        )
        assert r.status_code == 200, r.text
        validate_response(r.json(), "VizCoverageV1")
        assert r.json()["state"] == "UNKNOWN"
        assert r.json()["datasets"] == []
        assert r.json()["basis"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "path",
    [
        "/runs/no-id/visualization/target",
        "/runs/" + str(uuid4()) + "/visualization/candidates/no-id",
    ],
)
def test_invalid_resource_identifiers_are_rejected_before_store(tmp_path: Path, path: str) -> None:
    with client(tmp_path) as c:
        assert c.get("/api/v1" + path).status_code == 422


def test_optional_relief_accepts_null_but_rejects_paths_outside_delivery() -> None:
    path = REPO / "analogforge/src/analogforge/api/visualization_schemas/imagery-catalog.v1.schema.json"
    schema = json.loads(path.read_text())
    validator = Draft202012Validator(schema["properties"]["assets"]["items"]["properties"]["relief_path"])
    validator.validate(None)
    validator.validate("globe/deliveries/mars-relief-v1.jpg")
    for bad in ["globe/deliveries/../private.jpg", "https://example.invalid/image.jpg", "/private/image.jpg"]:
        with pytest.raises(ValidationError):
            validator.validate(bad)
