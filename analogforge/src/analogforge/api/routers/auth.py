"""OIDC sessions live outside the frozen 43 scientific operations."""

from __future__ import annotations

import secrets
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from analogforge.adapters.identity.local import IdentityService
from analogforge.adapters.identity.oidc import OIDCClient
from analogforge.api.dependencies import LOCAL_USER_ID, LOCAL_WORKSPACE_ID
from analogforge.api.errors import ApiError

router = APIRouter(prefix="/auth", include_in_schema=False)


def service(request: Request) -> IdentityService:
    return IdentityService(
        request.app.state.runtime.store, allowed_origins=tuple(request.app.state.settings.allowed_origins)
    )


def oidc(request: Request) -> OIDCClient:
    if request.app.state.settings.auth_mode != "oidc":
        raise ApiError("INVALID_TRANSITION", "OIDC login is disabled in local mode.", 409)
    injected = getattr(request.app.state, "oidc_client", None)
    if injected is not None:
        return cast(OIDCClient, injected)
    settings = request.app.state.settings
    return OIDCClient(
        request.app.state.runtime.store,
        issuer=settings.oidc_issuer_url,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.public_base_url.rstrip("/") + "/auth/callback",
        client_secret=settings.oidc_client_secret.get_secret_value(),
    )


def verified_session(request: Request) -> Any:
    token, workspace = request.cookies.get("af_session"), request.cookies.get("af_workspace")
    if not token or not workspace:
        raise ApiError("UNAUTHENTICATED", "A verified session is required.", 401)
    try:
        UUID(workspace)
    except ValueError as exc:
        raise ApiError("UNAUTHENTICATED", "A verified workspace session is required.", 401) from exc
    return service(request).authenticate(token, workspace)


@router.get("/login")
def login(request: Request, workspace_id: str) -> RedirectResponse:
    try:
        workspace = str(UUID(workspace_id))
    except ValueError as exc:
        raise ApiError("INPUT_INVALID", "The login workspace identifier is invalid.") from exc
    url = oidc(request).login(workspace)
    from urllib.parse import parse_qs, urlsplit

    state = parse_qs(urlsplit(url).query)["state"][0]
    response = RedirectResponse(url, status_code=303)
    response.set_cookie("af_login_state", state, max_age=600, secure=True, httponly=True, samesite="lax")
    response.set_cookie("af_login_workspace", workspace, max_age=600, secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/callback")
def callback(request: Request, state: str, code: str) -> RedirectResponse:
    expected, workspace = request.cookies.get("af_login_state"), request.cookies.get("af_login_workspace")
    if not expected or not workspace or not secrets.compare_digest(state, expected):
        raise ApiError("UNAUTHENTICATED", "The login state does not match this browser.", 401)
    try:
        UUID(workspace)
    except ValueError as exc:
        raise ApiError("UNAUTHENTICATED", "The login workspace is invalid.", 401) from exc
    if len(state) > 512 or len(code) > 8192:
        raise ApiError("INPUT_INVALID", "The login response exceeds the supported size.")
    claims = oidc(request).callback(workspace, state, code)
    store = request.app.state.runtime.store
    with store.transaction(workspace) as unit:
        matches = unit.list("users", {"issuer": claims["iss"], "subject": claims["sub"]})
    if len(matches) != 1:
        raise ApiError("FORBIDDEN", "An administrator must configure workspace membership before login.", 403)
    identity = service(request)
    role = identity.require_membership(workspace, matches[0]["id"])
    token, principal = identity.create_session(matches[0]["id"], workspace, role)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("af_session", token, secure=True, httponly=True, samesite="lax", max_age=28800)
    response.set_cookie(
        "af_workspace", principal.workspace_id, secure=True, httponly=True, samesite="lax", max_age=28800
    )
    response.delete_cookie("af_login_state", secure=True, httponly=True, samesite="lax")
    response.delete_cookie("af_login_workspace", secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/session")
def session(request: Request) -> JSONResponse:
    if request.app.state.settings.auth_mode == "local":
        document = {
            "authenticated": True,
            "user_id": LOCAL_USER_ID,
            "workspace_id": LOCAL_WORKSPACE_ID,
            "role": "OWNER",
            "csrf_token": None,
        }
    else:
        principal = verified_session(request)
        document = {
            "authenticated": True,
            "user_id": principal.user_id,
            "workspace_id": principal.workspace_id,
            "role": principal.role,
            "csrf_token": principal.csrf_token,
        }
    return JSONResponse(document, headers={"Cache-Control": "no-store"})


@router.post("/logout")
def logout(request: Request) -> Response:
    if request.app.state.settings.auth_mode != "local":
        principal = verified_session(request)
        if request.headers.get(
            "origin"
        ) not in request.app.state.settings.allowed_origins or not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), principal.csrf_token
        ):
            raise ApiError("FORBIDDEN", "A matching origin and CSRF token are required.", 403)
        service(request).revoke(request.cookies["af_session"], principal.workspace_id)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie("af_session", secure=True, httponly=True, samesite="lax")
    response.delete_cookie("af_workspace", secure=True, httponly=True, samesite="lax")
    return response
