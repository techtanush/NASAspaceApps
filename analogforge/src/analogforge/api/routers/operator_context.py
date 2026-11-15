"""Optional reviewed operator context API; deliberately outside the frozen 43 operations."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from analogforge.api.contracts import specification, validate
from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.errors import ApiError
from analogforge.api.security import json_nesting_depth, read_bounded_json_body
from analogforge.application import operator_context as context
from analogforge.application import runs
from analogforge.ports.hashing import bytes_sha256, canonical_sha256

router = APIRouter(prefix="/api/v1", include_in_schema=False)
Identity = Annotated[Principal, Depends(get_principal)]


def mutation(request: Request, principal: Principal) -> str:
    if principal.role not in {"OWNER", "EDITOR"}:
        raise ApiError("FORBIDDEN", "Viewer membership cannot modify operator context.", 403)
    key = request.headers.get("Idempotency-Key", "")
    return context.identifier(key)


async def body_json(request: Request) -> dict[str, Any]:
    try:
        raw = await read_bounded_json_body(request, 64000)
        if json_nesting_depth(raw, 16) > 16:
            raise ValueError("context nesting")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("context body")
        canonical_sha256(value)
        return value
    except (ValueError, RecursionError) as exc:
        raise ApiError("INPUT_INVALID", "The context request is invalid.") from exc


def json_response(value: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})


@router.post("/operator-documents", status_code=201)
async def upload_document(request: Request, principal: Identity) -> JSONResponse:
    key = mutation(request, principal)
    name = context.filename(request.headers.get("X-Upload-Filename", ""))
    media_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    content = await read_bounded_json_body(request, context.MAX_BYTES)
    digest = canonical_sha256({"filename": name, "media_type": media_type, "sha256": bytes_sha256(content)})
    rt = runtime(request)
    # A completed retry reuses its receipt before consuming another parse slot/rate reservation.
    with rt.store.transaction(principal.workspace_id) as unit:
        existing = unit.list("idempotency_requests", {"subject_id": principal.subject_id, "method": "POST",
                                                     "path": request.url.path, "key": key})
        if existing:
            if existing[0]["body_hash"] != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT", "This upload key belongs to different bytes or metadata.", 409)
            if existing[0].get("status") is not None:
                return json_response(existing[0]["response_json"], existing[0]["status"])
        context.reserve_upload(unit, principal.subject_id)
    extracted = await run_in_threadpool(context.parse_document, content, name, media_type)
    with rt.store.transaction(principal.workspace_id) as unit:
        previous = unit.idempotency_begin(principal.subject_id, "POST", request.url.path, key, digest)
        if previous:
            return json_response(previous[1], previous[0])
        result = context.create_document(unit, rt.blobs, content, name, media_type, extracted, principal.subject_id)
        unit.idempotency_complete(principal.subject_id, "POST", request.url.path, key, 201, result)
    return json_response(result, 201)


@router.get("/operator-documents/{document_id}")
def document(document_id: str, request: Request, principal: Identity) -> JSONResponse:
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        result = unit.require("operator_documents", context.identifier(document_id))
    return json_response(result)


@router.get("/operator-documents/{document_id}/content")
def original(document_id: str, request: Request, principal: Identity) -> Response:
    rt = runtime(request)
    with rt.store.transaction(principal.workspace_id) as unit:
        result = unit.require("operator_documents", context.identifier(document_id))
    content = rt.blobs.read_limited(result["original_sha256"], context.MAX_BYTES)
    return Response(content, media_type="application/octet-stream", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "attachment; filename=operator-document", "X-Artifact-SHA256": result["original_sha256"],
    })


@router.post("/operator-contexts", status_code=201)
async def create_context(request: Request, principal: Identity) -> JSONResponse:
    key = mutation(request, principal)
    raw = await body_json(request)
    try:
        body = context.ContextInput.model_validate(raw)
    except ValidationError as exc:
        raise ApiError("INPUT_INVALID", "The reviewed context does not satisfy operator-context.v1.") from exc
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        previous = unit.idempotency_begin(principal.subject_id, "POST", request.url.path, key, canonical_sha256(raw))
        if previous:
            return json_response(previous[1], previous[0])
        result = context.create_context(unit, body, principal.subject_id)
        unit.idempotency_complete(principal.subject_id, "POST", request.url.path, key, 201, result)
    return json_response(result, 201)


@router.get("/operator-contexts/{context_id}")
def get_context(context_id: str, request: Request, principal: Identity) -> JSONResponse:
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        result = context.context_public(unit, context_id)
    return json_response(result)


@router.get("/operator-context/preview")
def preview(request: Request, principal: Identity, mission_context_id: str | None = None,
            rover_context_id: str | None = None) -> JSONResponse:
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        result = context.snapshot(unit, mission_context_id, rover_context_id)
    return json_response(result)


@router.get("/missions/{target_id}/operator-context")
@router.get("/rover-revisions/{target_id}/operator-context")
def get_binding(target_id: str, request: Request, principal: Identity) -> JSONResponse:
    mission = "/missions/" in request.url.path
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        record = unit.require("missions" if mission else "rover_revisions", context.identifier(target_id))
        result = context.binding(unit, "MISSION_DRAFT" if mission else "ROVER_REVISION",
                                 record["current_draft_id"] if mission else record["id"])
        if mission:
            result["mission_revision"] = record["revision"]
    return json_response(result)


@router.post("/missions/{target_id}/operator-context", status_code=201)
@router.post("/rover-revisions/{target_id}/operator-context", status_code=201)
async def bind_context(target_id: str, request: Request, principal: Identity) -> JSONResponse:
    key = mutation(request, principal)
    raw = await body_json(request)
    try:
        body = context.BindingInput.model_validate(raw)
    except ValidationError as exc:
        raise ApiError("INPUT_INVALID", "The context binding is invalid.") from exc
    mission = "/missions/" in request.url.path
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        previous = unit.idempotency_begin(principal.subject_id, "POST", request.url.path, key, canonical_sha256(raw))
        if previous:
            return json_response(previous[1], previous[0])
        result = context.bind(unit, "MISSION_DRAFT" if mission else "ROVER_REVISION", target_id,
                              body, principal.subject_id)
        unit.idempotency_complete(principal.subject_id, "POST", request.url.path, key, 201, result)
    return json_response(result, 201)


@router.get("/mission-revisions/{target_id}/operator-context")
@router.get("/preparations/{target_id}/operator-context")
@router.get("/runs/{target_id}/operator-context")
def get_pin(target_id: str, request: Request, principal: Identity) -> JSONResponse:
    kind, table = next((kind, table) for segment, kind, table in (
        ("/mission-revisions/", "MISSION_REVISION", "mission_revisions"),
        ("/preparations/", "PREPARATION", "preparations"), ("/runs/", "RUN", "runs"),
    ) if segment in request.url.path)
    with runtime(request).store.transaction(principal.workspace_id) as unit:
        unit.require(table, context.identifier(target_id))
        result = context.pinned(unit, kind, target_id)
    return json_response(result)


@router.post("/operator-context/runs", status_code=202)
async def admit_run(request: Request, principal: Identity) -> JSONResponse:
    key = mutation(request, principal)
    raw = await body_json(request)
    try:
        body = context.AdmissionInput.model_validate(raw)
        operation = specification()["paths"]["/runs"]["post"]
        validate(body.run_request, operation["requestBody"]["content"]["application/json"]["schema"])
    except (ValidationError, SchemaValidationError, ValueError) as exc:
        raise ApiError("INPUT_INVALID", "The run request does not satisfy the existing admission contract.") from exc
    rt = runtime(request)
    with rt.store.transaction(principal.workspace_id) as unit:
        previous = unit.idempotency_begin(principal.subject_id, "POST", request.url.path, key, canonical_sha256(raw))
        if previous:
            return json_response(previous[1], previous[0])
        rover = body.run_request["rover_revision_id"]
        if rover:
            unit.require("rover_revisions", rover, lock=True)
        current = context.binding(unit, "ROVER_REVISION", rover)["context_id"] if rover else None
        if current != body.expected_rover_context_id:
            raise ApiError("REVISION_CONFLICT", "The reviewed rover context changed before run admission.", 409)
        result = runs.create(unit, principal.workspace_id, body.run_request, rt.settings,
                             rt.scenarios(), rt.science, rt.renderer)
        unit.idempotency_complete(principal.subject_id, "POST", request.url.path, key, 202, result)
    return json_response(result, 202)
