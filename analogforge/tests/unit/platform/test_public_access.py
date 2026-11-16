"""Public judging access has private cookie workspaces without accounts or shared ownership."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pydantic import ValidationError

from analogforge.adapters.identity.local import IdentityService
from analogforge.application.seed import seed_synthetic
from analogforge.db.schema import TABLES
from analogforge.db.store import PersistenceError, Store
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.integration.platform.test_journey_api import FIXTURES, journey_store
from tests.integration.platform.test_migrations import platform_store
from tests.support.factories import renderer_factory, science_factory

__all__ = ["journey_store", "platform_store"]

ORIGIN = "https://analogforge.example"


def public_app(store: Store, tmp_path: Path, **overrides: Any) -> Any:
    settings = Settings(
        _env_file=None,
        database_url=store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
        auth_mode="public",
        public_base_url=ORIGIN,
        allowed_origins=[ORIGIN],
        **overrides,
    )
    seed_synthetic(None, settings)
    return create_app(settings=settings, store=store, science=science_factory(), renderer=renderer_factory())


def mission_body() -> dict[str, Any]:
    content = json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())
    return {key: content[key] for key in ("name", "objective", "target")}


def mutation_headers(session: dict[str, Any], key: str | None = None) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"], "Idempotency-Key": key or str(uuid4())}


def post(client: TestClient, session: dict[str, Any], path: str, body: dict[str, Any], expected: int) -> dict[str, Any]:
    response = client.post(path, json=body, headers=mutation_headers(session))
    assert response.status_code == expected, response.text
    return response.json()


@pytest.mark.db
def test_public_sessions_are_private_reused_opaque_and_cookie_protected(journey_store: Store, tmp_path: Path) -> None:
    app = public_app(journey_store, tmp_path)
    with TestClient(app, base_url=ORIGIN) as first, TestClient(app, base_url=ORIGIN) as second:
        assert first.get("/api/v1/missions").status_code == 401
        response = first.get("/auth/session")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        session = response.json()
        other = second.get("/auth/session").json()
        assert session["authenticated"] is True and session["auth_mode"] == "public"
        assert session["role"] == "EDITOR"
        assert session["workspace_id"] != other["workspace_id"]
        assert session["user_id"] != other["user_id"] and session["csrf_token"] != other["csrf_token"]
        assert first.get("/auth/session").json() == session
        assert not first.get("/auth/session").headers.get_list("set-cookie")
        for cookie in response.headers.get_list("set-cookie"):
            assert all(flag in cookie.lower() for flag in ("secure", "httponly", "samesite=lax"))
        token = first.cookies["af_session"]
        assert token not in response.text
        with journey_store.transaction(session["workspace_id"]) as unit:
            stored = unit.list("sessions")
            assert len(stored) == 1 and stored[0]["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
            assert token not in json.dumps(stored)
        created = post(first, session, "/api/v1/missions", mission_body(), 201)
        assert first.get(f"/api/v1/missions/{created['id']}").status_code == 200
        assert second.get("/api/v1/missions").json()["items"] == []
        assert second.get(f"/api/v1/missions/{created['id']}").status_code == 404


@pytest.mark.db
def test_public_mutations_require_own_csrf_and_exact_origin(journey_store: Store, tmp_path: Path) -> None:
    app = public_app(journey_store, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        session = client.get("/auth/session").json()
        good = mutation_headers(session)
        for headers in (
            {key: value for key, value in good.items() if key != "X-CSRF-Token"},
            {**good, "X-CSRF-Token": "incorrect"},
            {**good, "Origin": "https://another.example"},
            {key: value for key, value in good.items() if key != "Origin"},
        ):
            assert client.post("/api/v1/missions", json=mission_body(), headers=headers).status_code == 403
        malformed = [(name.encode(), value.encode()) for name, value in good.items() if name != "X-CSRF-Token"]
        malformed.append((b"X-CSRF-Token", b"\xff"))
        assert client.post("/api/v1/missions", json=mission_body(), headers=malformed).status_code == 403
        assert client.post("/auth/logout", headers=malformed).status_code == 403
        assert client.get("/api/v1/missions").json()["items"] == []
        assert client.post("/api/v1/missions", json=mission_body(), headers=good).status_code == 201


@pytest.mark.db
def test_public_tamper_and_expired_sessions_recover_without_other_workspace_access(
    journey_store: Store,
    tmp_path: Path,
) -> None:
    app = public_app(journey_store, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client, TestClient(app, base_url=ORIGIN) as other:
        original = client.get("/auth/session").json()
        foreign = other.get("/auth/session").json()
        token = client.cookies["af_session"]
        for workspace in (foreign["workspace_id"], "not-a-workspace"):
            cookie = {"Cookie": f"af_session={token}; af_workspace={workspace}"}
            assert client.get("/api/v1/missions", headers=cookie).status_code == 401
        with journey_store.transaction(original["workspace_id"]) as unit:
            stored = unit.list("sessions")[0]
            stored["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
            unit.replace("sessions", stored["id"], stored)
        assert client.get("/api/v1/missions").status_code == 401
        recovered = client.get("/auth/session")
        assert recovered.status_code == 200
        assert recovered.json()["workspace_id"] not in {original["workspace_id"], foreign["workspace_id"]}
        assert client.get("/api/v1/missions").json()["items"] == []
        invalid = client.get("/auth/session", headers={"Cookie": "af_session=bad; af_workspace=not-a-workspace"})
        assert invalid.status_code == 200 and invalid.json()["workspace_id"] != recovered.json()["workspace_id"]


@pytest.mark.db
def test_public_session_refuses_cross_site_creation_without_consuming_capacity(
    journey_store: Store, tmp_path: Path
) -> None:
    app = public_app(journey_store, tmp_path, public_max_workspaces=1)
    with TestClient(app, base_url=ORIGIN) as client:
        for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://another.example"}):
            response = client.get("/auth/session", headers=headers)
            assert response.status_code == 403 and not response.headers.get_list("set-cookie")
        assert client.get("/auth/session").status_code == 200
        cookie = f"af_session={client.cookies['af_session']}; af_workspace={client.cookies['af_workspace']}"
        client.cookies.clear()
        response = client.get("/auth/session")
        assert response.status_code == 503 and response.json()["error"]["code"] == "PUBLIC_CAPACITY_REACHED"
        assert client.get("/auth/session", headers={"Cookie": cookie}).status_code == 200


@pytest.mark.db
def test_public_session_probe_never_allocates_even_at_capacity_or_with_invalid_cookies(
    journey_store: Store,
    tmp_path: Path,
) -> None:
    app = public_app(journey_store, tmp_path, public_max_workspaces=1)
    with TestClient(app, base_url=ORIGIN) as first, TestClient(app, base_url=ORIGIN) as visitor:
        anonymous = {"authenticated": False, "auth_mode": "public"}
        for headers in ({}, {"Cookie": "af_session=invalid; af_workspace=not-a-workspace"}):
            probe = visitor.get("/auth/session?create=false", headers=headers)
            assert probe.status_code == 200 and probe.json() == anonymous
            assert probe.headers["Cache-Control"] == "no-store" and not probe.headers.get_list("set-cookie")
        with journey_store.engine.connect() as connection:
            assert connection.execute(sa.select(sa.func.count()).select_from(TABLES["workspaces"])).scalar_one() == 0
        for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://another.example"}):
            assert visitor.get("/auth/session?create=false", headers=headers).status_code == 403
        created = first.get("/auth/session")
        assert created.status_code == 200
        reused = first.get("/auth/session?create=false")
        assert reused.status_code == 200 and reused.json() == created.json()
        assert not reused.headers.get_list("set-cookie")
        probe = visitor.get("/auth/session?create=false")
        assert probe.status_code == 200 and probe.json() == anonymous
        assert not probe.headers.get_list("set-cookie")
        assert visitor.get("/auth/session").status_code == 503
        with journey_store.engine.connect() as connection:
            assert connection.execute(sa.select(sa.func.count()).select_from(TABLES["workspaces"])).scalar_one() == 1


@pytest.mark.db
def test_public_health_probes_allocate_no_workspace_and_other_reads_stay_private(
    journey_store: Store, tmp_path: Path
) -> None:
    app = public_app(journey_store, tmp_path, public_max_workspaces=1)
    with TestClient(app, base_url=ORIGIN) as client:
        for _ in range(2):
            for path in ("/api/v1/health/live", "/api/v1/health/ready"):
                response = client.get(path)
                assert response.status_code == 200 and response.json() == {"status": "ok"}
                assert not response.headers.get_list("set-cookie")
        assert client.get("/api/v1/missions").status_code == 401
        assert client.get("/api/v1/capabilities").status_code == 401
        with journey_store.engine.connect() as connection:
            assert connection.execute(sa.select(sa.func.count()).select_from(TABLES["workspaces"])).scalar_one() == 0
        assert client.get("/auth/session").status_code == 200


@pytest.mark.db
def test_public_workspace_cap_is_atomic_across_parallel_visitors(journey_store: Store) -> None:
    identity = IdentityService(journey_store, allowed_origins=(ORIGIN,))

    def create(_: int) -> str:
        try:
            return identity.create_visitor_session(2)[1].workspace_id
        except PersistenceError as error:
            assert error.code == "PUBLIC_CAPACITY_REACHED"
            return "capacity"

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(create, range(6)))
    assert len({value for value in results if value != "capacity"}) == 2
    assert results.count("capacity") == 4
    with journey_store.engine.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(TABLES["workspaces"])).scalar_one() == 2


@pytest.mark.db
def test_public_mission_cap_serializes_parallel_requests_and_keeps_idempotent_replay(
    journey_store: Store,
    tmp_path: Path,
) -> None:
    app = public_app(journey_store, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        session = client.get("/auth/session").json()
        for _ in range(15):
            post(client, session, "/api/v1/missions", mission_body(), 201)
        keys = [str(uuid4()) for _ in range(4)]
        payload = mission_body()

        def create(index: int) -> tuple[int, str]:
            headers = mutation_headers(session, keys[index])
            response = client.post("/api/v1/missions", json=payload, headers=headers)
            return response.status_code, response.json().get("id", "")

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(create, range(4)))
        assert sorted(status for status, _ in responses) == [201, 429, 429, 429]
        with journey_store.transaction(session["workspace_id"]) as unit:
            assert len(unit.list("missions")) == 16
        # Replay the one successful command after the cap: it must not count as a new creation.
        successful = next(index for index, value in enumerate(responses) if value[0] == 201)
        replay = client.post("/api/v1/missions", json=payload, headers=mutation_headers(session, keys[successful]))
        assert replay.status_code == 201 and replay.json()["id"] == responses[successful][1]


@pytest.mark.db
def test_public_run_limit_keeps_existing_run_readable_and_retry_idempotent(
    journey_store: Store, tmp_path: Path
) -> None:
    app = public_app(journey_store, tmp_path, public_runs_per_workspace=1)
    content = json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())
    with TestClient(app, base_url=ORIGIN) as client:
        session = client.get("/auth/session").json()
        header = post(client, session, "/api/v1/missions", mission_body(), 201)
        revision = post(
            client,
            session,
            f"/api/v1/missions/{header['id']}/revisions",
            {
                "expected_revision": header["revision"],
                "contract": content,
            },
            201,
        )
        current = client.get(f"/api/v1/missions/{header['id']}").json()
        accepted = post(
            client,
            session,
            f"/api/v1/missions/{header['id']}/accept",
            {
                "expected_revision": current["revision"],
                "revision_id": revision["id"],
            },
            200,
        )
        body = {
            "mission_revision_id": accepted["id"],
            "rover_revision_id": None,
            "mode": "synthetic",
            "dataset_lock_id": "synthetic-policy-v1",
            "scenario_config_id": "synthetic-graph-regression-v1",
        }
        headers = mutation_headers(session)
        first = client.post("/api/v1/runs", json=body, headers=headers)
        assert first.status_code == 202, first.text
        replay = client.post("/api/v1/runs", json=body, headers=headers)
        assert replay.status_code == 202 and replay.json() == first.json()
        denied = client.post("/api/v1/runs", json=body, headers=mutation_headers(session))
        assert denied.status_code == 429 and denied.json()["error"]["code"] == "PUBLIC_USAGE_LIMIT"
        run_id = first.json()["run_id"]
        run = client.get(f"/api/v1/runs/{run_id}")
        assert run.status_code == 200
        cancelled = post(
            client,
            session,
            f"/api/v1/runs/{run_id}/actions",
            {
                "action_type": "CANCEL",
                "payload": {},
                "expected_revision": run.json()["revision"],
            },
            202,
        )
        assert cancelled["run_id"] == run_id
        assert client.get(f"/api/v1/runs/{run_id}").json()["state"] == "CANCELLED"


@pytest.mark.db
@pytest.mark.parametrize("operation", ["rover", "preparation"])
def test_public_rover_and_preparation_quotas_block_additional_resources(
    journey_store: Store,
    tmp_path: Path,
    operation: str,
) -> None:
    app = public_app(journey_store, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        session = client.get("/auth/session").json()
        if operation == "rover":
            path = "/api/v1/rovers"
            payload = json.loads((FIXTURES / "rovers" / "ares-1.json").read_text())
            expected = 201
            kind = "rovers"
        else:
            mission = post(client, session, "/api/v1/missions", mission_body(), 201)
            path = f"/api/v1/missions/{mission['id']}/fingerprint"
            payload = {"expected_revision": mission["revision"], "mode": "synthetic", "rover_revision_id": None}
            expected = 202
            kind = "preparations"
        for _ in range(16):
            post(client, session, path, payload, expected)
        denied = client.post(path, json=payload, headers=mutation_headers(session))
        assert denied.status_code == 429 and denied.json()["error"]["code"] == "PUBLIC_USAGE_LIMIT"
        with journey_store.transaction(session["workspace_id"]) as unit:
            assert len(unit.list(kind)) == 16


@pytest.mark.parametrize("url", ["http://public.example", "https://public.example/path", "https://u:p@public.example"])
def test_public_settings_require_https_origin_without_credentials(url: str) -> None:
    with pytest.raises(ValidationError, match="Public access"):
        Settings(_env_file=None, auth_mode="public", public_base_url=url, allowed_origins=[url])


def test_public_loopback_can_be_rehearsed_locally() -> None:
    settings = Settings(
        _env_file=None,
        auth_mode="public",
        public_base_url="http://127.0.0.1:5251",
        allowed_origins=["http://127.0.0.1:5251"],
    )
    assert settings.auth_mode == "public"
