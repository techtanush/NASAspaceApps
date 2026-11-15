"""Additive authenticated projection; GET never acquires provider data."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.errors import ApiError
from analogforge.application.environment import project


def build_environment_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/runs/{run_id}/environment", operation_id="getRunEnvironment", include_in_schema=False)
    def environment(
        run_id: str, request: Request, principal: Annotated[Principal, Depends(get_principal)],
    ) -> JSONResponse:
        try:
            run_id = str(UUID(run_id))
        except ValueError as exc:
            raise ApiError("INPUT_INVALID", "The run identifier is invalid.") from exc
        rt = runtime(request)
        result = project(rt.store, rt.blobs, request.app.state.settings, principal.workspace_id, run_id)
        return JSONResponse(result, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return router
