"""Server-established identity and application dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from fastapi import Request

LOCAL_WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
LOCAL_USER_ID = "22222222-2222-4222-8222-222222222222"


@dataclass(frozen=True)
class Principal:
    workspace_id: str
    subject_id: str
    role: str = "OWNER"


def get_principal(request: Request) -> Principal:
    provider = request.app.state.identity_provider
    if provider is not None:
        return cast(Principal, provider(request))
    if request.app.state.settings.auth_mode != "local":
        from analogforge.adapters.identity.local import IdentityService
        from analogforge.api.errors import ApiError

        token = request.cookies.get("af_session")
        workspace_id = request.cookies.get("af_workspace")
        if not token or not workspace_id:
            raise ApiError("UNAUTHENTICATED", "A verified session is required.", 401)
        try:
            UUID(workspace_id)
        except ValueError as exc:
            raise ApiError("UNAUTHENTICATED", "A verified workspace session is required.", 401) from exc
        settings = request.app.state.settings
        service = IdentityService(request.app.state.runtime.store, allowed_origins=tuple(settings.allowed_origins))
        verified = service.authenticate(token, workspace_id)
        if request.method == "POST":
            service.protect_mutation(verified, request.headers.get("X-CSRF-Token"), request.headers.get("origin"))
        return Principal(verified.workspace_id, verified.user_id, verified.role)
    return Principal(LOCAL_WORKSPACE_ID, LOCAL_USER_ID)


def runtime(request: Request) -> Any:
    return request.app.state.runtime
