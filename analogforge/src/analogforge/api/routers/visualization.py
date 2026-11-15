"""Authenticated, read-only visualization projections. Never acquires source bytes in HTTP."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.errors import ApiError
from analogforge.api.visualization_contracts import OPERATIONS, effective_specification, validate_response


def _uuid(request: Request, name: str) -> str:
    try:
        return str(UUID(request.path_params[name]))
    except (ValueError, KeyError) as exc:
        raise ApiError("INPUT_INVALID", "A visualization resource identifier is invalid.") from exc


def _coverage_query(request: Request) -> tuple[str, tuple[float, float, float, float], str, str | None]:
    query = request.query_params
    allowed = {"body", "bbox", "scenario_config_id", "dataset_lock_id"}
    if set(query) - allowed or any(len(query.getlist(name)) != 1 for name in query):
        raise ApiError("INPUT_INVALID", "Visualization coverage parameters are ambiguous or unsupported.")
    if not {"body", "bbox", "scenario_config_id"}.issubset(query):
        raise ApiError("INPUT_INVALID", "Body, bounding box and scenario are required.")
    if any(len(value) > (256 if name == "bbox" else 128) for name, value in query.items()):
        raise ApiError("INPUT_INVALID", "A visualization coverage parameter exceeds its bound.")
    try:
        values = tuple(float(value.strip()) for value in query["bbox"].split(","))
        if len(values) != 4 or not all(math.isfinite(value) for value in values):
            raise ValueError("finite four-component box required")
    except ValueError as exc:
        raise ApiError("INPUT_INVALID", "The visualization bounding box must contain four finite coordinates.") from exc
    return (
        query["body"],
        (values[0], values[1], values[2], values[3]),
        query["scenario_config_id"],
        query.get("dataset_lock_id"),
    )


def _dispatch(request: Request, principal: Principal, operation: str, model: str | None) -> JSONResponse:
    rt = runtime(request)
    request.state.workspace_id = principal.workspace_id
    if operation == "getVisualizationCapabilities":
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "enabled": True,
            "coverage": True,
            "regional_detail": True,
            "benchmarks": True,
            "imagery_catalog_path": "globe/data/catalog.v1.json",
            "imagery_purpose": "VISUAL_CONTEXT_ONLY",
            "openapi_path": "/api/v1/visualization/openapi.json",
        }
    elif operation == "getVisualizationOpenApi":
        payload = effective_specification()
    elif operation == "getVisualizationCoverage":
        from analogforge.application.visualization_coverage import get_visualization_coverage

        body, bbox, scenario, lock = _coverage_query(request)
        payload = get_visualization_coverage(
            rt.settings, body=body, bbox=bbox, scenario_config_id=scenario, dataset_lock_id=lock
        ).model_dump(mode="json")
    else:
        run_id = _uuid(request, "run_id")
        candidate = _uuid(request, "candidate_id") if "candidate_id" in request.path_params else None
        with rt.store.transaction(principal.workspace_id) as uow:
            if operation == "getVisualizationBenchmarks":
                from analogforge.application.visualization_benchmarks import site_benchmarks

                if candidate is None:
                    raise ApiError("INPUT_INVALID", "A candidate is required.")
                payload = site_benchmarks(uow, rt.blobs, run_id, candidate)
            else:
                from analogforge.application.visualization_detail import site_detail

                payload = site_detail(uow, rt.blobs, run_id, candidate)
    if model:
        validate_response(payload, model)
    return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})


def _endpoint(operation: str, model: str | None) -> Callable[..., JSONResponse]:
    def endpoint(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> JSONResponse:
        return _dispatch(request, principal, operation, model)

    return endpoint


def build_visualization_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    for path, operation, model in OPERATIONS:
        router.add_api_route(path, _endpoint(operation, model), methods=["GET"], operation_id=operation)
    return router
