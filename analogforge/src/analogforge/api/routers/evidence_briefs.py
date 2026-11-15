"""Optional authenticated current-evidence PDF. The frozen passport export stays unchanged."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from analogforge.api.dependencies import Principal, get_principal, runtime
from analogforge.api.errors import ApiError
from analogforge.application.evidence_brief import build_packet, build_snapshot, pdf_digest, render_pdf

router = APIRouter(prefix="/api/v1", include_in_schema=False)


@router.get("/runs/{run_id}/test-brief.pdf")
def download_test_packet(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Response:
    if request.query_params:
        raise ApiError("INPUT_INVALID", "The test brief does not accept query parameters.")
    try:
        run_id = str(UUID(request.path_params["run_id"]))
    except ValueError as exc:
        raise ApiError("INPUT_INVALID", "A test brief identifier is invalid.") from exc
    rt = runtime(request)
    request.state.workspace_id = principal.workspace_id
    with rt.store.transaction(principal.workspace_id) as unit:
        snapshot = build_packet(unit, rt.blobs, run_id)
    content = render_pdf(snapshot)
    return Response(content, media_type="application/pdf", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="analogforge-mission-test-brief-{run_id[:8]}.pdf"',
        "X-Artifact-SHA256": pdf_digest(content), "X-Evidence-Snapshot-SHA256": snapshot["snapshot_sha256"],
        "X-Run-Revision": str(snapshot["run"]["revision"]),
    })


@router.get("/runs/{run_id}/candidates/{candidate_id}/test-plan")
def get_site_test_plan(
    request: Request, response: Response, principal: Annotated[Principal, Depends(get_principal)],
) -> dict[str, Any]:
    if request.query_params:
        raise ApiError("INPUT_INVALID", "The test plan does not accept query parameters.")
    try:
        run_id, candidate_id = (str(UUID(request.path_params[name])) for name in ("run_id", "candidate_id"))
    except ValueError as exc:
        raise ApiError("INPUT_INVALID", "A test plan identifier is invalid.") from exc
    rt = runtime(request)
    request.state.workspace_id = principal.workspace_id
    with rt.store.transaction(principal.workspace_id) as unit:
        snapshot = build_snapshot(unit, rt.blobs, run_id, candidate_id)
    response.headers["Cache-Control"] = "private, no-store"
    return {**snapshot["test_plan"], "run_id": run_id, "run_revision": snapshot["run"]["revision"],
            "discovery_method": snapshot["candidate"].get("discovery_method"),
            "screened_count": (snapshot.get("search_scope") or {}).get("screened_count"),
            "dataset_lock_id": snapshot["run"].get("dataset_lock_id")}


@router.get("/runs/{run_id}/candidates/{candidate_id}/evidence-brief.pdf")
def download_evidence_brief(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> Response:
    if request.query_params:
        raise ApiError("INPUT_INVALID", "The evidence PDF does not accept query parameters.")
    try:
        run_id, candidate_id = (str(UUID(request.path_params[name])) for name in ("run_id", "candidate_id"))
    except ValueError as exc:
        raise ApiError("INPUT_INVALID", "An evidence PDF identifier is invalid.") from exc
    rt = runtime(request)
    request.state.workspace_id = principal.workspace_id
    with rt.store.transaction(principal.workspace_id) as unit:
        snapshot = build_snapshot(unit, rt.blobs, run_id, candidate_id)
    content = render_pdf(snapshot)
    return Response(content, media_type="application/pdf", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="analogforge-evidence-brief-{run_id[:8]}-{candidate_id[:8]}.pdf"',
        "X-Artifact-SHA256": pdf_digest(content), "X-Evidence-Snapshot-SHA256": snapshot["snapshot_sha256"],
        "X-Run-Revision": str(snapshot["run"]["revision"]),
    })
