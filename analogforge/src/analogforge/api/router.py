"""All frozen operations dispatch to persisted, workspace-scoped application services."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from jsonschema import ValidationError

from analogforge.api.contracts import public_document, specification, validate
from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.errors import ApiError
from analogforge.api.security import read_bounded_json_body
from analogforge.api.sse import stream
from analogforge.application import missions, rovers, runs
from analogforge.jobs.events import event_cursor
from analogforge.ports.hashing import canonical_sha256

LISTS = {
    "listMissions": ("missions", "MissionHeader"),
    "listRovers": ("rovers", "RoverProfile"),
    "listRuns": ("runs", "RunSnapshot"),
    "listEarthAnalogCandidate": ("candidates", "EarthAnalogCandidate"),
    "listQualificationDimension": ("qualifications", "QualificationDimension"),
    "listVerificationTest": ("tests", "VerificationTest"),
    "listAgentActions": ("agent_actions", "AgentAction"),
    "listCritiques": ("evidence", "EvidenceRecord"),
    "listDisplayLayers": ("display_layers", "DisplayLayerManifest"),
}
READS = {
    "getMission": ("missions", "MissionHeader"),
    "getMissionDraft": ("mission_drafts", "MissionDraft"),
    "getMissionRevision": ("mission_revisions", "MissionTestContract"),
    "getRoverRevision": ("rover_revisions", "RoverProfile"),
    "getRun": ("runs", "RunSnapshot"),
    "getEarthAnalogCandidate": ("candidates", "EarthAnalogCandidate"),
    "getQualificationDimension": ("qualifications", "QualificationDimension"),
    "getVerificationTest": ("tests", "VerificationTest"),
    "getTestResult": ("test_results", "TestResult"),
    "getCompositePortfolio": ("portfolios", "CompositePortfolio"),
    "getEvidenceRecord": ("evidence", "EvidenceRecord"),
    "getAnalogPassport": ("passports", "AnalogPassport"),
    "getTargetProfile": ("target_profiles", "PlanetaryTargetProfile"),
    "getToolReceipt": ("tool_receipts", "ToolReceipt"),
    "getReview": ("reviews", "ReviewRequest"),
}


def validate_parameters(request: Request, operation: dict[str, Any]) -> None:
    for parameter in operation.get("parameters", []):
        if "$ref" in parameter:
            parameter = specification()["components"]["parameters"][parameter["$ref"].split("/")[-1]]
        location = parameter["in"]
        source = {"path": request.path_params, "query": request.query_params, "header": request.headers}[location]
        raw = source.get(parameter["name"])
        if raw is None:
            if parameter.get("required"):
                raise ApiError(
                    "INPUT_INVALID", "A required request parameter is missing.", details={"field": parameter["name"]}
                )
            continue
        schema = parameter["schema"]
        try:
            value = int(raw) if schema.get("type") == "integer" else raw
            validate(value, schema)
        except (ValueError, ValidationError) as exc:
            raise ApiError(
                "INPUT_INVALID", "A request parameter is invalid.", details={"field": parameter["name"]}
            ) from exc


def job_public(document: dict[str, Any]) -> dict[str, Any]:
    error = document.get("error")
    if error and "error" not in error:
        error = ApiError(error.get("code", "SYSTEM"), "The queued operation could not complete.", 503).envelope()
    return {
        "id": document["id"],
        "state": document["state"],
        "progress_step": document.get("progress_step", document.get("kind", "QUEUED")),
        "run_id": document.get("run_id"),
        "preparation_id": document.get("preparation_id"),
        "proposed_revision_id": document.get("proposed_revision_id"),
        "error": error,
    }


def paginated(rows: list[dict[str, Any]], model: str, request: Request) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (row.get("created_at", ""), row["id"]))
    cursor = request.query_params.get("cursor")
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if value["workspace"] != request.state.workspace_id:
                raise ValueError("cursor scope")
            rows = [row for row in rows if (row.get("created_at", ""), row["id"]) > tuple(value["after"])]
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError("INPUT_INVALID", "The list cursor is invalid for this workspace.") from exc
    limit = int(request.query_params.get("limit", "25"))
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1]
        next_cursor = base64.urlsafe_b64encode(
            json.dumps(
                {"workspace": request.state.workspace_id, "after": [last.get("created_at", ""), last["id"]]}
            ).encode()
        ).decode()
    return {"items": [public_document(row, model) for row in page], "next_cursor": next_cursor}


def mutate(
    uow: Any, operation_id: str, record_id: str | None, body: dict[str, Any], principal: Principal, rt: Any
) -> tuple[int, dict[str, Any]]:
    workspace_id = principal.workspace_id
    if operation_id == "createMission":
        return 201, missions.create(uow, workspace_id, body)
    if operation_id == "saveMissionDraft":
        return 201, missions.save_draft(uow, str(record_id), body)
    if operation_id == "createMissionRevision":
        return 201, missions.propose(uow, str(record_id), body["contract"], body["expected_revision"])
    if operation_id == "acceptMissionRevision":
        return 200, missions.accept(uow, str(record_id), body, principal.subject_id)
    if operation_id == "createRover":
        return 201, rovers.create(uow, workspace_id, body)
    if operation_id == "createRoverRevision":
        return 201, rovers.create(uow, workspace_id, body["profile"], str(record_id), body["expected_revision"])
    if operation_id == "prepareMissionFingerprint":
        mission = uow.require("missions", str(record_id))
        missions.check_revision(mission, body["expected_revision"])
        runs.require_live(rt.settings, body["mode"])
        if body["rover_revision_id"]:
            uow.require("rover_revisions", body["rover_revision_id"])
        preparation_id = missions.uid()
        uow.create(
            "preparations",
            {
                "id": preparation_id,
                "mission_draft_revision_id": mission["current_draft_id"],
                "mode": body["mode"],
                "status": "QUEUED",
            },
        )
        job = uow.enqueue("PREPARE_FINGERPRINT", {**body, "mission_id": record_id}, preparation_id=preparation_id)
        return 202, {
            "preparation_id": preparation_id,
            "job_id": job["id"],
            "mission_id": record_id,
            "revision": mission["revision"],
        }
    if operation_id == "createRun":
        return 202, runs.create(uow, workspace_id, body, rt.settings, rt.scenarios(), rt.science, rt.renderer)
    if operation_id == "submitRunAction":
        snapshot = rt.engine.apply_action(
            str(record_id), workspace_id, body["action_type"], body["payload"], body["expected_revision"], uow=uow
        )
        queued = uow.list("jobs", {"run_id": record_id, "state": "QUEUED"})
        return 202, {
            "run_id": record_id,
            "job_id": queued[-1]["id"] if queued else None,
            "command_id": missions.uid(),
            "revision": snapshot["revision"],
        }
    raise ApiError("INVALID_TRANSITION", "The requested mutation is unavailable.", 409)


async def dispatch(request: Request, principal: Principal, operation: dict[str, Any]) -> Response:
    rt = runtime(request)
    operation_id = operation["operationId"]
    request.state.workspace_id = principal.workspace_id
    validate_parameters(request, operation)
    if operation_id == "healthLive":
        return JSONResponse({"status": "ok"})
    if operation_id == "healthReady":
        if not rt.store.health():
            raise ApiError("DATABASE_UNAVAILABLE", "Database migrations or connection are unavailable.", 503)
        return JSONResponse({"status": "ok"})
    if operation_id == "getCapabilities":
        from analogforge.application.capabilities import get_capabilities

        return JSONResponse(get_capabilities(rt.settings, rt.store))
    if operation_id == "getScenarioConfig":
        scenario = rt.scenarios().get(request.path_params["id"])
        if scenario is None:
            raise ApiError("NOT_FOUND", "Scenario not found.", 404)
        return JSONResponse(public_document({"id": request.path_params["id"], **scenario}, "ScenarioConfig"))
    if request.method == "POST":
        if principal.role == "VIEWER":
            raise ApiError("FORBIDDEN", "Viewer membership cannot submit commands.", 403)
        key = request.headers.get("Idempotency-Key")
        if key is None:
            raise ApiError("INPUT_INVALID", "Idempotency-Key is required.")
        try:
            UUID(key)
            raw = await read_bounded_json_body(request)
            body = json.loads(raw)
            canonical_sha256(body)
            body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
            validate(body, body_schema)
        except (ValueError, ValidationError) as exc:
            raise ApiError("INPUT_INVALID", "The request body does not satisfy the public contract.") from exc
        with rt.store.transaction(principal.workspace_id) as uow:
            previous = uow.idempotency_begin(
                principal.subject_id, request.method, request.url.path, key, canonical_sha256(body)
            )
            if previous is not None:
                return JSONResponse(previous[1], status_code=previous[0])
            status, result = mutate(uow, operation_id, request.path_params.get("id"), body, principal, rt)
            uow.idempotency_complete(principal.subject_id, request.method, request.url.path, key, status, result)
        return JSONResponse(result, status_code=status)
    with rt.store.transaction(principal.workspace_id) as uow:
        if operation_id in READS:
            kind, model = READS[operation_id]
            record = uow.require(kind, request.path_params["id"])
            if kind == "mission_revisions":
                record = missions.accepted_contract(uow, record["id"])
            return JSONResponse(public_document(record, model))
        if operation_id == "getRover":
            header = uow.require("rovers", request.path_params["id"])
            return JSONResponse(
                public_document(uow.require("rover_revisions", header["latest_revision_id"]), "RoverProfile")
            )
        if operation_id == "getJob":
            return JSONResponse(job_public(uow.require("jobs", request.path_params["id"])))
        if operation_id in LISTS:
            kind, model = LISTS[operation_id]
            filters = {
                name: value
                for name, value in request.query_params.items()
                if name in {"run_id", "candidate_id", "target_profile_id"}
            }
            if "run_id" in filters:
                uow.require("runs", filters["run_id"])
            if operation_id == "listCritiques":
                # Latest CRITIQUE evidence per issue (each state change is a new immutable record).
                issues = uow.list("critiques", {k: v for k, v in filters.items() if k in {"run_id", "candidate_id"}})
                rows = [uow.require("evidence", issue["evidence_id"]) for issue in issues if issue.get("evidence_id")]
                return JSONResponse(paginated(rows, model, request))
            rows = uow.list(kind, filters)
            if operation_id == "listRovers":
                rows = [uow.require("rover_revisions", row["latest_revision_id"]) for row in rows]
            if operation_id == "listDisplayLayers":
                return JSONResponse({"items": [public_document(row, model) for row in rows], "next_cursor": None})
            return JSONResponse(paginated(rows, model, request))
        if operation_id == "getCompatibility":
            run_id = request.query_params["run_id"]
            run = uow.require("runs", run_id)
            if run["rover_revision_id"] is None:
                raise ApiError("ROVER_REQUIRED", "This run qualifies sites without rover verification.", 409)
            rows = uow.list("compatibility", {"run_id": run_id, "candidate_id": request.query_params["candidate_id"]})
            if not rows:
                raise ApiError("NOT_FOUND", "Compatibility has not been computed.", 404)
            return JSONResponse(public_document(rows[-1], "CompatibilityAssessment"))
        if operation_id == "streamRunEvents":
            run_id = request.path_params["id"]
            uow.require("runs", run_id)
            after = event_cursor(int(request.query_params.get("after", "0")), request.headers.get("Last-Event-ID"))
            rt.store.events(principal.workspace_id, run_id, after=after)
        elif operation_id == "getArtifact":
            sha = request.path_params["sha256"]
            refs = uow.list("evidence", {"artifact_sha256": sha}) + uow.list("export_artifacts", {"artifact_hash": sha})
            if not refs:
                raise ApiError("NOT_FOUND", "Artifact not found.", 404)
            content = rt.blobs.read(sha)
            media_type = "application/octet-stream"
            headers = {
                "ETag": f'"{sha}"',
                "X-Artifact-SHA256": sha,
                "X-Content-Type-Options": "nosniff",
                "Accept-Ranges": "none",
            }
            return Response(content, media_type=media_type, headers=headers)
        elif operation_id == "getPassportExport":
            passport_id, fmt = request.path_params["id"], request.path_params["format"]
            passport = uow.require("passports", passport_id)
            matches = uow.list("export_artifacts", {"passport_id": passport_id, "format": fmt})
            if matches:
                artifact = matches[-1]
                digest = artifact.get("artifact_hash", artifact.get("sha256"))
                content = rt.blobs.read(digest)
                return Response(
                    content,
                    media_type=artifact.get("media_type", "application/octet-stream"),
                    headers={
                        "Content-Disposition": f'attachment; filename="{artifact["filename"]}"',
                        "ETag": f'"{digest}"',
                        "X-Artifact-SHA256": digest,
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            queued = uow.list("jobs", {"run_id": passport["run_id"], "kind": "EXPORT_PASSPORT", "state": "QUEUED"})
            job = (
                queued[0]
                if queued
                else uow.enqueue(
                    "EXPORT_PASSPORT", {"passport_id": passport_id, "format": fmt}, run_id=passport["run_id"]
                )
            )
            return JSONResponse(job_public(job), status_code=202, headers={"Retry-After": "1"})
        else:
            raise ApiError("NOT_FOUND", "The requested resource does not exist.", 404)
    return StreamingResponse(
        stream(request, rt.store, principal.workspace_id, run_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def build_route_group(operation_ids: frozenset[str]) -> APIRouter:
    """Register a category without copying or drifting its wire declarations."""
    router = APIRouter()

    def endpoint_factory(operation: dict[str, Any]) -> Any:
        async def endpoint(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Response:
            return await dispatch(request, principal, operation)

        return endpoint

    for path, methods in specification()["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post"} and operation["operationId"] in operation_ids:
                router.add_api_route(
                    path,
                    endpoint_factory(operation),
                    methods=[method.upper()],
                    operation_id=operation["operationId"],
                    name=operation["operationId"],
                )
    return router


def build_router() -> APIRouter:
    from analogforge.api.routers import (
        artifacts,
        capabilities,
        configuration,
        evidence,
        health,
        jobs,
        missions,
        passports,
        reads,
        rovers,
        runs,
    )

    router = APIRouter(prefix="/api/v1")
    for category in (
        missions,
        rovers,
        runs,
        jobs,
        reads,
        evidence,
        passports,
        artifacts,
        capabilities,
        health,
        configuration,
    ):
        # add_api_route keeps inspection and generated clients independent of
        # FastAPI's deferred include-router representation.
        for route in category.build_router().routes:
            if not isinstance(route, APIRoute):
                raise TypeError("Contract route group contains an unsupported route")
            router.add_api_route(
                route.path,
                route.endpoint,
                methods=sorted(route.methods or {"GET"}),
                operation_id=route.operation_id,
                name=route.name,
            )
    return router
