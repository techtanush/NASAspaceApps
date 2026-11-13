"""Public reads and lists fetch only what they return.

Found by load measurement of the merged release candidate: listing runs took ~240 ms because every page loaded the whole
table (a run row stores ~350 kB of internal payload, the public document ~4 kB) and sliced it in Python, and
``GET /passports/{id}`` read 1.7 MB to return 22 kB. The public output is unchanged; the SQL is not.
"""

from __future__ import annotations

import base64
import collections
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from analogforge.api.contracts import public_document, specification
from analogforge.api.dependencies import Principal
from analogforge.api.router import INTERNAL_PAYLOAD_KEYS, LISTS, READS
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.integration.platform.test_journey_api import journey_store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["journey_store", "platform_store"]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "kit"


def public_properties(model: str) -> set[str]:
    schemas = specification()["components"]["schemas"]
    schema = schemas[model]
    while "$ref" in schema:
        schema = schemas[schema["$ref"].split("/")[-1]]
    return set(schema.get("properties", {}))


def test_no_excluded_key_is_ever_a_public_property():
    """Excluding a public key would silently change the API; this fails the build if the contract and table drift."""
    models: dict[str, set[str]] = collections.defaultdict(set)
    for operations in (LISTS, READS):
        for kind, model in operations.values():
            models[kind].add(model)
    for kind, keys in INTERNAL_PAYLOAD_KEYS.items():
        assert kind in models, f"{kind} is excluded but no public operation reads it"
        for model in models[kind]:
            assert not set(keys) & public_properties(model), f"{kind}: {set(keys) & public_properties(model)} is public"


def make_client(store: Store, tmp_path: Path, workspace: str | None = None) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url=store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    provider = (lambda _request: Principal(workspace, "operator")) if workspace else None
    if workspace is None:
        seed_synthetic(store, settings)  # the local workspace and user that API-created records belong to
    return TestClient(create_app(settings=settings, store=store, identity_provider=provider))


def statements(store: Store, action: Any) -> list[str]:
    seen: list[str] = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):  # type: ignore[no-untyped-def]
        seen.append(" ".join(statement.split()))

    sa.event.listen(store.engine, "before_cursor_execute", record)
    try:
        action()
    finally:
        sa.event.remove(store.engine, "before_cursor_execute", record)
    return seen


@pytest.mark.db
def test_run_reads_and_lists_drop_internal_payloads_in_sql_and_keep_the_public_document(journey_store: Store, tmp_path):
    workspace, run = seed_run(journey_store)
    with journey_store.transaction(workspace) as unit:
        stored = unit.require("runs", run["id"], lock=True)
        stored["runtime"] = {"blob": "r" * 60_000}
        stored["audit_payload"] = {"blob": "a" * 60_000}
        unit.replace("runs", run["id"], stored, stored.get("revision"))
    client = make_client(journey_store, tmp_path, workspace)
    with journey_store.transaction(workspace) as unit:
        full = unit.require("runs", run["id"])
    assert "runtime" in full and "audit_payload" in full

    single: list[Any] = []
    listing: list[Any] = []
    single_sql = statements(journey_store, lambda: single.append(client.get(f"/api/v1/runs/{run['id']}")))
    list_sql = statements(journey_store, lambda: listing.append(client.get("/api/v1/runs", params={"limit": 5})))

    assert single[0].status_code == 200 and listing[0].status_code == 200
    expected = public_document(full, "RunSnapshot")
    assert single[0].json() == expected
    assert listing[0].json()["items"] == [expected]
    for sql, bounded in ((single_sql, False), (list_sql, True)):
        selects = [s for s in sql if s.startswith("SELECT") and "FROM runs" in s]
        assert selects and all("document_json - CAST" in s for s in selects), selects
        assert all("LIMIT" in s for s in selects) == bounded


@pytest.mark.db
def test_a_list_page_loads_one_extra_row_not_the_table(journey_store: Store, tmp_path):
    client = make_client(journey_store, tmp_path)
    body = json.loads((FIXTURES / "missions" / "mission-mars-mobility.json").read_text())
    for index in range(7):
        response = client.post(
            "/api/v1/missions",
            json={"name": f"page-{index}", "objective": body["objective"], "target": body["target"]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
    fetched: list[Any] = []

    def page() -> None:
        fetched.append(client.get("/api/v1/missions", params={"limit": 2}))

    selects = [s for s in statements(journey_store, page) if s.startswith("SELECT") and "FROM missions" in s]
    assert fetched[0].status_code == 200 and len(fetched[0].json()["items"]) == 2 and fetched[0].json()["next_cursor"]
    assert len(selects) == 1 and "LIMIT" in selects[0]
    with journey_store.engine.connect() as connection:  # the query is bounded by the limit it was given
        assert connection.execute(sa.text("select count(*) from missions")).scalar_one() >= 7


@pytest.mark.db
@pytest.mark.parametrize("limit", [1, 2, 3, 5, 7, 100])
def test_keyset_pagination_visits_every_row_once_in_stable_order(journey_store: Store, tmp_path, limit):
    client = make_client(journey_store, tmp_path)
    body = json.loads((FIXTURES / "missions" / "mission-mars-mobility.json").read_text())
    created = []
    for index in range(7):
        response = client.post(
            "/api/v1/missions",
            json={"name": f"keyset-{limit}-{index}", "objective": body["objective"], "target": body["target"]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        created.append(response.json()["id"])
    everything = [row["id"] for row in client.get("/api/v1/missions", params={"limit": 100}).json()["items"]]
    assert set(created) <= set(everything) and len(everything) == len(set(everything))
    walked: list[str] = []
    cursor: str | None = None
    for _ in range(len(everything) + 2):
        params: dict[str, Any] = {"limit": limit, **({"cursor": cursor} if cursor else {})}
        document = client.get("/api/v1/missions", params=params).json()
        walked += [row["id"] for row in document["items"]]
        cursor = document["next_cursor"]
        if cursor is None:
            break
    assert cursor is None and walked == everything[: len(walked)] and walked == everything


@pytest.mark.db
@pytest.mark.parametrize(
    "position",
    [
        ["2026-11-13T00:00:00Z"],
        ["2026-11-13T00:00:00Z", "not-a-uuid"],
        ["yesterday", "00000000-0000-4000-8000-000000000000"],
        [1, 2],
        "text",
        None,
        ["2026-11-13T00:00:00Z", "00000000-0000-4000-8000-000000000000", "extra"],
    ],
)
def test_a_cursor_with_a_malformed_position_is_invalid_not_a_server_error(journey_store: Store, tmp_path, position):
    client = make_client(journey_store, tmp_path)
    workspace = client.get("/auth/session").json()["workspace_id"]
    cursor = base64.urlsafe_b64encode(json.dumps({"workspace": workspace, "after": position}).encode()).decode()
    response = client.get("/api/v1/missions", params={"cursor": cursor})
    assert response.status_code == 422 and response.json()["error"]["code"] == "INPUT_INVALID"


@pytest.mark.db
def test_a_cursor_from_another_workspace_is_refused(journey_store: Store, tmp_path):
    client = make_client(journey_store, tmp_path)
    cursor = base64.urlsafe_b64encode(
        json.dumps({"workspace": str(uuid4()), "after": ["2026-11-13T00:00:00Z", str(uuid4())]}).encode()
    ).decode()
    assert client.get("/api/v1/missions", params={"cursor": cursor}).status_code == 422
