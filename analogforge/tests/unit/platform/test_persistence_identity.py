"""Signed fake-issuer tokens, replay protection, sessions and CSRF enforcement."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import jwt
import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric import rsa

from analogforge.adapters.identity.local import IdentityService, Principal
from analogforge.adapters.identity.oidc import OIDCClient
from analogforge.db.schema import TABLES
from analogforge.db.store import PersistenceError, Store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.fixture
def rsa_key() -> Any:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(key: Any, **changes: Any) -> tuple[str, dict[str, Any]]:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://issuer.example",
        "aud": "analogforge",
        "sub": "member",
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "nonce": "expected",
    }
    claims.update(changes)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public["kid"] = "key-1"
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "key-1"}), {"keys": [public]}


def test_oidc_signature_issuer_audience_expiry_nonce_are_required(rsa_key: Any) -> None:
    oidc = OIDCClient(
        Store("postgresql+psycopg://localhost/unused"),
        issuer="https://issuer.example",
        client_id="analogforge",
        redirect_uri="https://app.example/auth/callback",
    )
    token, keys = _token(rsa_key)
    assert oidc.validate_id_token(token, keys, "expected")["sub"] == "member"
    for changes in (
        {"iss": "https://attacker.example"},
        {"aud": "another-client"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"nonce": "different"},
    ):
        bad, _ = _token(rsa_key, **changes)
        with pytest.raises(PersistenceError):
            oidc.validate_id_token(bad, keys, "expected")
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged, _ = _token(wrong)
    with pytest.raises(PersistenceError):
        oidc.validate_id_token(forged, keys, "expected")


@pytest.mark.db
def test_opaque_sessions_csrf_origin_viewer_and_revocation(platform_store: Store) -> None:
    workspace, _ = seed_run(platform_store)
    identity = IdentityService(platform_store, allowed_origins=("http://127.0.0.1:8001",))
    user = str(uuid4())
    with platform_store.transaction(workspace) as unit:
        unit.create("users", {"id": user, "issuer": "https://issuer.example", "subject": user})
        unit.create("workspace_memberships", {"user_id": user, "role": "EDITOR"})
    token, principal = identity.create_session(user, workspace, "EDITOR")
    assert identity.authenticate(token, workspace) == principal
    identity.protect_mutation(principal, principal.csrf_token, "http://127.0.0.1:8001")
    for csrf, origin in ((None, "http://127.0.0.1:8001"), (principal.csrf_token, "https://attacker.example")):
        with pytest.raises(PersistenceError):
            identity.protect_mutation(principal, csrf, origin)
    with pytest.raises(PersistenceError):
        identity.protect_mutation(
            Principal(principal.user_id, workspace, "VIEWER", principal.csrf_token),
            principal.csrf_token,
            "http://127.0.0.1:8001",
        )
    identity.revoke(token, workspace)
    with pytest.raises(PersistenceError):
        identity.authenticate(token, workspace)


@pytest.mark.db
def test_existing_session_uses_current_membership_and_loses_access_on_removal(platform_store: Store) -> None:
    workspace, _ = seed_run(platform_store)
    user = str(uuid4())
    with platform_store.transaction(workspace) as unit:
        unit.create("users", {"id": user, "issuer": "https://issuer.example", "subject": user})
        membership = unit.create("workspace_memberships", {"user_id": user, "role": "EDITOR"})
    identity = IdentityService(platform_store, allowed_origins=("https://app.example",))
    token, _ = identity.create_session(user, workspace, "EDITOR")
    with platform_store.transaction(workspace) as unit:
        membership["role"] = "VIEWER"
        unit.replace("workspace_memberships", membership["id"], membership)
    principal = identity.authenticate(token, workspace)
    assert principal.role == "VIEWER"
    with pytest.raises(PersistenceError) as denied:
        identity.protect_mutation(principal, principal.csrf_token, "https://app.example")
    assert denied.value.code == "AUTHORIZATION_FAILED"
    with platform_store.transaction(workspace) as unit:
        table = TABLES["workspace_memberships"]
        unit.connection.execute(sa.delete(table).where(table.c.id == membership["id"]))
    with pytest.raises(PersistenceError) as removed:
        identity.authenticate(token, workspace)
    assert removed.value.code == "AUTHENTICATION_REQUIRED"


@pytest.mark.db
def test_oidc_fake_discovery_requires_pinned_endpoints(platform_store: Store) -> None:
    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "issuer": "https://issuer.example",
                "authorization_endpoint": "https://attacker.example/auth",
                "token_endpoint": "https://issuer.example/token",
                "jwks_uri": "https://issuer.example/keys",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(response))
    oidc = OIDCClient(
        platform_store,
        issuer="https://issuer.example",
        client_id="analogforge",
        redirect_uri="https://app.example/auth/callback",
        client=client,
    )
    with pytest.raises(PersistenceError) as error:
        oidc.discovery()
    assert error.value.code == "OIDC_CONFIGURATION_INVALID"
