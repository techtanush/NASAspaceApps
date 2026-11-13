"""HTTP boundary hardening found by spec-driven fuzzing of the merged release candidate.

Every case here was a real defect: deeply nested JSON escaped as a bare 500 (RecursionError is not a ValueError),
unmatched routes answered with FastAPI's default body instead of the frozen error envelope, an unexpected failure
produced a non-contract 500, and the interactive docs were on by default (Swagger UI loads its scripts from a CDN).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.security import MAX_JSON_DEPTH, json_nesting_depth
from analogforge.db.store import Store
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.unit.platform.test_http_security import error_document, journey_store, platform_store

__all__ = ["journey_store", "platform_store"]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "kit"
WRITE_ROUTES = [
    "/api/v1/missions",
    "/api/v1/rovers",
    "/api/v1/runs",
    f"/api/v1/missions/{uuid4()}/revisions",
    f"/api/v1/missions/{uuid4()}/fingerprint",
    f"/api/v1/missions/{uuid4()}/accept",
    f"/api/v1/missions/{uuid4()}/drafts",
    f"/api/v1/rovers/{uuid4()}/revisions",
    f"/api/v1/runs/{uuid4()}/actions",
]


def client_for(store: Store, tmp_path: Path, **overrides: Any) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url=store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
        **overrides,
    )
    return TestClient(create_app(settings=settings, store=store), raise_server_exceptions=False)


def post(client: TestClient, route: str, body: bytes) -> Any:
    headers = {"Idempotency-Key": str(uuid4()), "Content-Type": "application/json"}
    return client.post(route, content=body, headers=headers)


def nested(depth: int) -> bytes:
    return b"[" * depth + b"]" * depth


@pytest.mark.db
@pytest.mark.parametrize("route", WRITE_ROUTES)
@pytest.mark.parametrize("depth", [200, 900, 20_000])
def test_runaway_json_nesting_is_a_contract_error_on_every_write_operation(
    journey_store: Store, tmp_path: Path, route: str, depth: int
) -> None:
    response = post(client_for(journey_store, tmp_path), route, nested(depth))
    document = error_document(response, 422)
    assert document["error"]["code"] == "INPUT_INVALID"
    assert response.headers["X-Request-ID"] == document["error"]["request_id"]


def test_the_depth_guard_counts_only_structure_not_text():
    assert json_nesting_depth(b'{"a":[{"b":[1,2,3]}]}') == 4
    assert json_nesting_depth(b'{"text":"[[[[[[[[[[ ]]]]]]]]]] \\" [["}') == 1
    assert json_nesting_depth(nested(MAX_JSON_DEPTH)) == MAX_JSON_DEPTH
    assert json_nesting_depth(b"") == 0


def test_the_depth_limit_leaves_wide_headroom_over_every_legitimate_contract_body():
    deepest = 0
    for path in sorted(FIXTURES.rglob("*.json")):
        deepest = max(deepest, json_nesting_depth(path.read_bytes()))
    assert 0 < deepest <= MAX_JSON_DEPTH // 2, f"deepest legitimate body is {deepest}, limit {MAX_JSON_DEPTH}"


@pytest.mark.db
def test_a_runaway_list_cursor_is_invalid_not_a_server_error(journey_store: Store, tmp_path):
    cursor = base64.urlsafe_b64encode(nested(20_000)).decode()
    response = client_for(journey_store, tmp_path).get("/api/v1/missions", params={"cursor": cursor})
    assert error_document(response, 422)["error"]["code"] == "INPUT_INVALID"


@pytest.mark.db
def test_an_oversized_body_is_refused_with_the_envelope_before_it_is_parsed(journey_store: Store, tmp_path):
    body = json.dumps({"name": "A" * 400_000}).encode()
    response = post(client_for(journey_store, tmp_path), "/api/v1/missions", body)
    assert error_document(response, 413)["error"]["code"] == "INPUT_TOO_LARGE"


@pytest.mark.db
@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("GET", "/api/v1/does-not-exist", 404, "NOT_FOUND"),
        ("GET", "/nothing-here", 404, "NOT_FOUND"),
        ("GET", "/api/v1/missions/a%2Fb", 404, "NOT_FOUND"),
        ("GET", "/api/v1/artifacts/..%2F..%2Fetc%2Fpasswd", 404, "NOT_FOUND"),
        ("DELETE", "/api/v1/runs", 405, "METHOD_NOT_ALLOWED"),
        ("PUT", "/api/v1/missions", 405, "METHOD_NOT_ALLOWED"),
    ],
)
def test_unmatched_routes_and_methods_use_the_frozen_error_envelope(
    journey_store: Store, tmp_path: Path, method: str, path: str, status: int, code: str
) -> None:
    response = client_for(journey_store, tmp_path).request(method, path)
    document = error_document(response, status)
    assert document["error"]["code"] == code
    assert UUID(document["error"]["request_id"]) and response.headers["X-Request-ID"] == document["error"]["request_id"]
    assert document["error"]["retryable"] is False and document["error"]["details"] == {}
    if status == 405:
        assert response.headers.get("Allow")


@pytest.mark.db
def test_interactive_docs_are_off_by_default_and_opt_in(journey_store: Store, tmp_path):
    client = client_for(journey_store, tmp_path)
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        error_document(client.get(path), 404)
    enabled = client_for(journey_store, tmp_path, api_docs=True)
    assert enabled.get("/docs").status_code == 200
    assert enabled.get("/openapi.json").json()["info"]["title"].startswith("AnalogForge")


@pytest.mark.db
def test_an_unexpected_failure_is_an_enveloped_500_that_reveals_nothing(journey_store: Store, tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    app = create_app(settings=settings, store=journey_store)

    @app.get("/__boom")
    async def boom() -> None:
        raise RuntimeError("internal detail postgresql://user:hunter2@db/prod /srv/analogforge/secret.py")

    response = TestClient(app, raise_server_exceptions=False).get("/__boom")
    document = error_document(response, 500)
    assert document["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text and "/srv/" not in response.text and "RuntimeError" not in response.text
