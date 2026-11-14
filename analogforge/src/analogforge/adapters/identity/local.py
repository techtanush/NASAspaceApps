"""Opaque server-side sessions and exact-origin cookie request protection."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from analogforge.db.store import NotFound, PersistenceError, Store


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    role: str
    csrf_token: str


class IdentityService:
    def __init__(self, store: Store, *, allowed_origins: tuple[str, ...], session_seconds: int = 28800) -> None:
        self.store = store
        self.allowed_origins = allowed_origins
        self.session_seconds = session_seconds

    def create_session(self, user_id: str, workspace_id: str, role: str) -> tuple[str, Principal]:
        if role not in {"OWNER", "EDITOR", "VIEWER"}:
            raise PersistenceError("AUTHORIZATION_FAILED", "Unknown membership role")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.store.transaction(workspace_id) as unit:
            unit.create(
                "sessions",
                {
                    "id": str(uuid4()),
                    "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                    "user_id": user_id,
                    "role": role,
                    "csrf_token": csrf,
                    "expires_at": datetime.now(UTC) + timedelta(seconds=self.session_seconds),
                },
            )
        return token, Principal(user_id, workspace_id, role, csrf)

    def authenticate(self, token: str, workspace_id: str) -> Principal:
        with self.store.transaction(workspace_id) as unit:
            sessions = unit.list("sessions", {"token_hash": hashlib.sha256(token.encode()).hexdigest()})
        if len(sessions) != 1:
            raise PersistenceError("AUTHENTICATION_REQUIRED", "Session is invalid")
        session = sessions[0]
        if datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00")) <= datetime.now(UTC):
            raise PersistenceError("AUTHENTICATION_REQUIRED", "Session expired")
        return Principal(session["user_id"], workspace_id, session["role"], session["csrf_token"])

    def revoke(self, token: str, workspace_id: str) -> None:
        with self.store.transaction(workspace_id) as unit:
            sessions = unit.list("sessions", {"token_hash": hashlib.sha256(token.encode()).hexdigest()})
            if not sessions:
                return
            session = sessions[0]
            session["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
            unit.replace("sessions", session["id"], session)

    def protect_mutation(self, principal: Principal, csrf: str | None, origin: str | None) -> None:
        if principal.role == "VIEWER":
            raise PersistenceError("AUTHORIZATION_FAILED", "Viewer cannot change workspace data")
        if origin not in self.allowed_origins or csrf is None or not secrets.compare_digest(csrf, principal.csrf_token):
            raise PersistenceError("CSRF_INVALID", "Origin and CSRF token must match the active session")

    def local_principal(self, workspace_id: str, user_id: str) -> Principal:
        self.store.ensure_workspace(UUID(workspace_id), "Local development")
        with self.store.transaction(workspace_id) as unit:
            user = unit.get("users", user_id)
            if user is None:
                unit.create("users", {"id": user_id, "issuer": "local", "subject": user_id})
            memberships = unit.list("workspace_memberships", {"user_id": user_id})
            if not memberships:
                unit.create("workspace_memberships", {"user_id": user_id, "role": "OWNER"})
        return Principal(user_id, workspace_id, "OWNER", "")

    def require_membership(self, workspace_id: str, user_id: str) -> str:
        with self.store.transaction(workspace_id) as unit:
            rows = unit.list("workspace_memberships", {"user_id": user_id})
        if not rows:
            raise NotFound()
        return str(rows[0]["role"])
