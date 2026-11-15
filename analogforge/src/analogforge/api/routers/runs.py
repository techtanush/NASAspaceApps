"""Runs HTTP operations selected from the immutable contract."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.router import build_route_group
from analogforge.application.activity import page

OPERATION_IDS = frozenset(["createRun", "listRuns", "getRun", "submitRunAction", "streamRunEvents"])


def build_router() -> APIRouter:
    return build_route_group(OPERATION_IDS)


def build_activity_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/runs/{run_id}/activity", operation_id="getRunActivity", include_in_schema=False)
    def activity(
        run_id: str,
        request: Request,
        principal: Annotated[Principal, Depends(get_principal)],
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
    ) -> JSONResponse:
        # Optional UI projection; the immutable scientific API/event envelopes remain unchanged.
        from uuid import UUID

        from analogforge.api.errors import ApiError

        try:
            run_id = str(UUID(run_id))
        except ValueError as exc:
            raise ApiError("INPUT_INVALID", "The run identifier is invalid.") from exc
        result = page(runtime(request).store, principal.workspace_id, run_id, limit=limit, cursor=cursor)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    return router
