"""Actual HTTP boundaries: cookies, fake-issuer OIDC, artifacts and workspace authorization."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from analogforge.adapters.identity.local import IdentityService
from analogforge.adapters.identity.oidc import OIDCClient
from analogforge.api.dependencies import Principal
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.contracts.platform.test_transport_complete import validate_document
from tests.integration.platform.test_journey_api import FIXTURES, journey_store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["journey_store", "platform_store"]


def error_document(response: httpx.Response, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    value: dict[str, Any] = response.json()
    validate_document(value, {"$ref": "#/components/schemas/ErrorEnvelope"})
    assert ".runtime" not in response.text and "postgresql" not in response.text
    return value


@pytest.mark.db
def test_artifact_ranges_missing_bytes_tamper_and_workspace_authorization(journey_store: Store, tmp_path: Path) -> None:
    workspace, run = seed_run(journey_store)
    foreign, _ = seed_run(journey_store)
    actor = {"workspace": workspace}
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    seed_synthetic(None, settings)
    app = create_app(
        settings=settings,
        store=journey_store,
        identity_provider=lambda _request: Principal(actor["workspace"], "operator"),
    )
    blob = app.state.runtime.blobs.put_bytes(b"0123456789", "application/octet-stream")
    with journey_store.transaction(workspace) as unit:
        unit.create(
            "evidence",
            {
                "run_id": run["id"],
                "kind": "DERIVED",
                "artifact_sha256": blob.sha256,
                "artifact_media_type": blob.media_type,
            },
        )
    url = f"/api/v1/artifacts/{blob.sha256}"
    with TestClient(app) as client:
        full = client.get(url)
        assert full.status_code == 200 and full.content == b"0123456789"
        assert full.headers["ETag"] == f'"{blob.sha256}"'
        assert full.headers["X-Content-Type-Options"] == "nosniff"
        partial = client.get(url, headers={"Range": "bytes=2-4"})
        assert partial.status_code == 200 and partial.content == b"0123456789"
        assert "Content-Range" not in partial.headers
        suffix = client.get(url, headers={"Range": "bytes=-2"})
        assert suffix.status_code == 200 and suffix.content == b"0123456789"
        for value in ("bytes=99-100", "bytes=4-2", "bytes=0-1,3-4", "items=0-2", "bytes=-0", "bytes=-"):
            ignored = client.get(url, headers={"Range": value})
            assert ignored.status_code == 200 and ignored.content == b"0123456789"
        actor["workspace"] = foreign
        error_document(client.get(url), 404)
        error_document(client.get(f"/api/v1/runs/{run['id']}"), 404)
        actor["workspace"] = workspace
        private_file = app.state.runtime.blobs.path(blob.sha256)
        private_file.write_bytes(b"tampered")
        assert error_document(client.get(url), 422)["error"]["code"] == "SOURCE_CHECKSUM_MISMATCH"
        private_file.unlink()
        assert error_document(client.get(url), 503)["error"]["code"] == "SOURCE_UNAVAILABLE"


@pytest.mark.db
def test_sse_rejects_invalid_cursors_before_streaming_and_honors_header(journey_store: Store, tmp_path: Path) -> None:
    workspace, run = seed_run(journey_store)
    with journey_store.transaction(workspace) as unit:
        unit.append_event(run["id"], "evidence.created", {}, "synthetic")
        current = unit.require("runs", run["id"])
        unit.replace("runs", run["id"], {**current, "state": "COMPLETED"}, current["revision"])
        terminal = unit.append_event(run["id"], "run.state_changed", {}, "synthetic")
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    app = create_app(
        settings=settings, store=journey_store, identity_provider=lambda _request: Principal(workspace, "operator")
    )
    path = f"/api/v1/runs/{run['id']}/events"
    with TestClient(app) as client:
        response = client.get(path + "?after=0", headers={"Last-Event-ID": "1"})
        assert response.status_code == 200
        assert "id:1\n" not in response.text and f"id:{terminal['seq']}\n" in response.text
        for cursor in ("abc", "-1", "1.2"):
            error_document(client.get(path, headers={"Last-Event-ID": cursor}), 422)
        assert error_document(client.get(path + "?after=1000"), 410)["error"]["code"] == "EVENT_CURSOR_EXPIRED"


@pytest.mark.db
def test_local_http_origin_and_request_limits(journey_store: Store, tmp_path: Path) -> None:
    workspace, _ = seed_run(journey_store)
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
        allowed_origins=["https://workbench.example"],
    )
    seed_synthetic(None, settings)
    app = create_app(
        settings=settings, store=journey_store, identity_provider=lambda _request: Principal(workspace, "operator")
    )
    content = json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())
    body = {key: content[key] for key in ("name", "objective", "target")}
    with TestClient(app) as client:
        headers = {"Idempotency-Key": str(uuid4()), "Origin": "https://attacker.example"}
        error_document(client.post("/api/v1/missions", json=body, headers=headers), 403)
        error_document(client.post("/api/v1/missions", json=body), 422)
        headers = {"Idempotency-Key": str(uuid4()), "Origin": "https://workbench.example"}
        excessive = {**body, "objective": "x" * 262145}
        error_document(client.post("/api/v1/missions", json=excessive, headers=headers), 413)
        assert client.post("/api/v1/missions", json=body, headers=headers).status_code == 201


@pytest.mark.db
def test_oidc_real_http_login_callback_pkce_membership_csrf_and_logout(journey_store: Store, tmp_path: Path) -> None:
    workspace = str(uuid4())
    user = str(uuid4())
    journey_store.ensure_workspace(workspace)
    with journey_store.transaction(workspace) as unit:
        unit.create("users", {"id": user, "issuer": "https://issuer.example", "subject": "configured-member"})
        unit.create("workspace_memberships", {"user_id": user, "role": "EDITOR"})
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
        auth_mode="oidc",
        session_secret="s" * 32,
        oidc_issuer_url="https://issuer.example",
        oidc_client_id="analogforge",
        oidc_client_secret=uuid4().hex,
        public_base_url="https://workbench.example",
        allowed_origins=["https://workbench.example"],
    )
    seed_synthetic(None, settings)
    app = create_app(settings=settings, store=journey_store)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_key["kid"] = "issuer-test-key"
    flow: dict[str, str] = {"subject": "configured-member"}

    def issuer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example",
                    "authorization_endpoint": "https://issuer.example/authorize",
                    "token_endpoint": "https://issuer.example/token",
                    "jwks_uri": "https://issuer.example/jwks",
                },
            )
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [public_key]})
        assert request.url.path == "/token" and request.method == "POST"
        form = parse_qs(request.content.decode())
        verifier = form["code_verifier"][0]
        assert (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            == flow["challenge"]
        )
        assert form["grant_type"] == ["authorization_code"]
        assert form["redirect_uri"] == ["https://workbench.example/auth/callback"]
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "iss": "https://issuer.example",
                "aud": "analogforge",
                "sub": flow["subject"],
                "nonce": flow["nonce"],
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "issuer-test-key"},
        )
        return httpx.Response(200, json={"id_token": token})

    app.state.oidc_client = OIDCClient(
        journey_store,
        issuer="https://issuer.example",
        client_id="analogforge",
        redirect_uri="https://workbench.example/auth/callback",
        client_secret=uuid4().hex,
        client=httpx.Client(transport=httpx.MockTransport(issuer)),
    )
    with TestClient(app, base_url="https://workbench.example", follow_redirects=False) as client:
        error_document(client.get("/api/v1/missions"), 401)
        login = client.get(f"/auth/login?workspace_id={workspace}")
        assert login.status_code == 303 and login.headers["Cache-Control"] == "no-store"
        params = parse_qs(urlsplit(login.headers["location"]).query)
        flow.update(nonce=params["nonce"][0], challenge=params["code_challenge"][0])
        assert params["code_challenge_method"] == ["S256"]
        error_document(client.get("/auth/callback?state=wrong&code=test-code"), 401)
        callback = client.get(f"/auth/callback?state={params['state'][0]}&code=test-code")
        assert callback.status_code == 303, callback.text
        session_cookies = [value for value in callback.headers.get_list("set-cookie") if "af_session=" in value]
        assert session_cookies and all(
            flag in session_cookies[0].lower() for flag in ("secure", "httponly", "samesite=lax")
        )
        session = client.get("/auth/session")
        assert session.status_code == 200 and session.headers["Cache-Control"] == "no-store"
        assert session.json()["role"] == "EDITOR" and session.json()["workspace_id"] == workspace
        csrf = session.json()["csrf_token"]
        body = {
            key: json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())[key]
            for key in ("name", "objective", "target")
        }
        headers = {"Idempotency-Key": str(uuid4()), "Origin": "https://workbench.example"}
        error_document(client.post("/api/v1/missions", json=body, headers=headers), 403)
        headers["X-CSRF-Token"] = csrf
        assert client.post("/api/v1/missions", json=body, headers=headers).status_code == 201
        error_document(client.post("/auth/logout", headers={"Origin": "https://workbench.example"}), 403)
        assert client.post("/auth/logout", headers=headers).status_code == 204
        error_document(client.get("/auth/session"), 401)
        # A valid issuer signature is insufficient to join the workspace automatically.
        flow["subject"] = "not-administratively-configured"
        login = client.get(f"/auth/login?workspace_id={workspace}")
        params = parse_qs(urlsplit(login.headers["location"]).query)
        flow.update(nonce=params["nonce"][0], challenge=params["code_challenge"][0])
        error_document(client.get(f"/auth/callback?state={params['state'][0]}&code=test-code"), 403)
        error_document(client.get("/auth/session"), 401)


@pytest.mark.db
def test_oidc_cookie_workspace_tamper_viewer_and_expiry(journey_store: Store, tmp_path: Path) -> None:
    workspace, _ = seed_run(journey_store)
    foreign, _ = seed_run(journey_store)
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
        auth_mode="oidc",
        session_secret="s" * 32,
        oidc_issuer_url="https://issuer.example",
        oidc_client_id="analogforge",
        oidc_client_secret=uuid4().hex,
        public_base_url="https://workbench.example",
        allowed_origins=["https://workbench.example"],
    )
    app = create_app(settings=settings, store=journey_store)
    identity = IdentityService(journey_store, allowed_origins=("https://workbench.example",))
    token, principal = identity.create_session(str(uuid4()), workspace, "VIEWER")
    with TestClient(app, base_url="https://workbench.example") as client:
        cookie = f"af_session={token}; af_workspace={workspace}"
        assert client.get("/api/v1/missions", headers={"Cookie": cookie}).status_code == 200
        error_document(
            client.post(
                "/api/v1/missions",
                json={},
                headers={
                    "Cookie": cookie,
                    "Origin": "https://workbench.example",
                    "X-CSRF-Token": principal.csrf_token,
                    "Idempotency-Key": str(uuid4()),
                },
            ),
            403,
        )
        for fake_workspace in (foreign, "not-a-uuid"):
            error_document(
                client.get(
                    "/api/v1/missions", headers={"Cookie": f"af_session={token}; af_workspace={fake_workspace}"}
                ),
                401,
            )
        identity.revoke(token, workspace)
        error_document(client.get("/api/v1/missions", headers={"Cookie": cookie}), 401)
