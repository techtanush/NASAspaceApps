"""OIDC authorization-code + PKCE flow with pinned issuer and signed ID tokens."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

from analogforge.db.store import PersistenceError, Store


class OIDCClient:
    def __init__(
        self,
        store: Store,
        *,
        issuer: str,
        client_id: str,
        redirect_uri: str,
        client_secret: str | None = None,
        client: httpx.Client | None = None,
        allow_loopback_issuer: bool = False,
    ) -> None:
        parsed = urlsplit(issuer)
        if parsed.scheme != "https" and not (allow_loopback_issuer and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise PersistenceError("OIDC_CONFIGURATION_INVALID", "OIDC issuer must use HTTPS")
        self.store, self.issuer, self.client_id = store, issuer.rstrip("/"), client_id
        self.redirect_uri, self.client_secret = redirect_uri, client_secret
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)

    def _json(self, method: str, url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            response = self.client.request(method, url, data=data)
            response.raise_for_status()
            value = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PersistenceError(
                "IDENTITY_PROVIDER_UNAVAILABLE", "The configured identity provider did not return a valid response"
            ) from exc
        if not isinstance(value, dict):
            raise PersistenceError("IDENTITY_PROVIDER_UNAVAILABLE", "The identity provider returned an invalid object")
        return value

    def discovery(self) -> dict[str, Any]:
        result = self._json("GET", f"{self.issuer}/.well-known/openid-configuration")
        if result.get("issuer") != self.issuer:
            raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC discovery issuer mismatch")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            endpoint = urlsplit(result.get(key, ""))
            issuer = urlsplit(self.issuer)
            if (endpoint.scheme, endpoint.netloc) != (issuer.scheme, issuer.netloc):
                raise PersistenceError(
                    "OIDC_CONFIGURATION_INVALID", "OIDC endpoints must use the configured issuer origin"
                )
        return result

    def login(self, workspace_id: str) -> str:
        metadata = self.discovery()
        state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        with self.store.transaction(workspace_id) as unit:
            unit.create(
                "login_flows",
                {
                    "state_hash": hashlib.sha256(state.encode()).hexdigest(),
                    "nonce": nonce,
                    "verifier": verifier,
                    "consumed": False,
                    "expires_at": datetime.now(UTC) + timedelta(minutes=10),
                },
            )
        return (
            str(metadata["authorization_endpoint"])
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "scope": "openid profile",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    def callback(self, workspace_id: str, state: str, code: str) -> dict[str, Any]:
        digest = hashlib.sha256(state.encode()).hexdigest()
        with self.store.transaction(workspace_id) as unit:
            rows = unit.list("login_flows", {"state_hash": digest})
            if len(rows) != 1:
                raise PersistenceError("AUTHENTICATION_REQUIRED", "Unknown OIDC state")
            flow = unit.require("login_flows", rows[0]["id"], lock=True)
            if flow["consumed"] or datetime.fromisoformat(flow["expires_at"].replace("Z", "+00:00")) <= datetime.now(
                UTC
            ):
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC state expired or was already used")
            flow["consumed"] = True
            unit.replace("login_flows", flow["id"], flow)
        metadata = self.discovery()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": flow["verifier"],
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        token = self._json("POST", metadata["token_endpoint"], payload).get("id_token")
        if not isinstance(token, str):
            raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC response has no ID token")
        keys = self._json("GET", metadata["jwks_uri"])
        return self.validate_id_token(token, keys, flow["nonce"])

    def validate_id_token(self, token: str, jwks: Mapping[str, Any], nonce: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"RS256", "ES256"}:
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC token algorithm is not permitted")
            keys = jwks.get("keys")
            if not isinstance(keys, list) or not all(isinstance(key, dict) for key in keys):
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC signing key set is invalid")
            candidates = [key for key in keys if key.get("kid") == header.get("kid")]
            if len(candidates) != 1:
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC signing key is unknown")
            key = jwt.PyJWK.from_dict(candidates[0], algorithm=header["alg"])
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=[header["alg"]],
                audience=self.client_id,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud", "nonce"]},
            )
            if not secrets.compare_digest(str(claims["nonce"]), nonce):
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC nonce mismatch")
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC subject is invalid")
            if isinstance(claims.get("aud"), list) and len(claims["aud"]) > 1 and claims.get("azp") != self.client_id:
                raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC authorized-party mismatch")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise PersistenceError("AUTHENTICATION_REQUIRED", "OIDC ID token verification failed") from exc
