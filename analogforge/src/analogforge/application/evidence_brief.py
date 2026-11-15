"""A private current-evidence snapshot and bounded offline PDF, never a passport publication."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from analogforge.api.errors import ApiError
from analogforge.application.activity import FAILURE_SUMMARIES, failure_code
from analogforge.application.site_test_plan import field_plan
from analogforge.application.visualization_benchmarks import site_benchmarks
from analogforge.application.visualization_detail import (
    authorized_subject,
    registered_json,
    scoped_record,
    site_detail,
)
from analogforge.db.store import NotFound, PersistenceError
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    AnalyzeCandidatePayload,
    CharacterizeTargetPayload,
    ScreenCandidatesPayload,
)

MAX_INPUT = 8 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024
MEMORY_MIB = 512
_render_slot = threading.BoundedSemaphore(1)


def _analysis(
    uow: Any, blobs: Any, run: dict[str, Any], subject: dict[str, Any] | None,
    aoi: dict[str, Any], operations: list[dict[str, Any]], *, target: bool,
) -> dict[str, Any]:
    unavailable = {"available": False, "reason": "No compatible registered analysis summary is available."}
    if subject is None:
        return unavailable
    model = CharacterizeTargetPayload if target else AnalyzeCandidatePayload
    operation_name = "CHARACTERIZE_TARGET" if target else "ANALYZE_CANDIDATE"
    reference_key = "profile_evidence" if target else "analysis_evidence"
    for operation in reversed(operations):
        if operation.get("operation") != operation_name or operation.get("status") not in {"SUCCEEDED", "LIMITED"}:
            continue
        try:
            if any(operation.get(k) != run.get(k) for k in ("workspace_id", "run_id", "mode")):
                continue
            request = operation["request"]
            inputs = request["inputs"]
            if target:
                if inputs.get("target") != aoi:
                    continue
            else:
                candidate = inputs.get("candidate", {})
                if (candidate.get("candidate_id") != subject["id"] or candidate.get("aoi") != aoi
                        or candidate.get("window_id") != subject.get("window_id")):
                    continue
            policy = request.get("source_policy", {})
            pinned_policy = run.get("runtime", {}).get("dataset_policy_sha256")
            if (request.get("mode") != run["mode"] or policy.get("policy_id") != run.get("dataset_lock_id")
                    or (pinned_policy is not None and policy.get("policy_sha256") != pinned_policy)):
                continue
            receipt = scoped_record(uow, "tool_receipts", operation["receipt_id"], run)
            if (receipt.get("status") != "SUCCEEDED" or canonical_sha256(request) != receipt.get("input_sha256")
                    or receipt.get("tool_name") != ("characterize_target" if target else "analyze_earth_candidate")):
                continue
            payload = model.model_validate(operation["payload"]).model_dump(mode="json")
            analysis_id = payload[reference_key]["evidence_id"]
            own = set(subject.get("evidence_ids", []))
            if analysis_id not in own or analysis_id not in operation.get("evidence_ids", []):
                continue
            source = scoped_record(uow, "evidence", analysis_id, run)
            if source.get("body") != aoi["body"]:
                continue
            for identifier in operation.get("evidence_ids", []):
                if identifier not in own or identifier not in receipt.get("evidence_ids", []):
                    continue
                evidence = scoped_record(uow, "evidence", identifier, run)
                if (evidence.get("body") != aoi["body"] or evidence.get("artifact_media_type") != "application/json"
                        or evidence.get("algorithm_id") != ("characterize-target" if target else "analysis-summary")
                        or (not target and analysis_id not in evidence.get("input_evidence_ids", []))):
                    continue
                raw = model.model_validate(registered_json(uow, blobs, evidence, run)).model_dump(mode="json")
                facts = {k: v for k, v in payload.items() if k != reference_key}
                if canonical_sha256(facts) != canonical_sha256({k: v for k, v in raw.items() if k != reference_key}):
                    continue
                histogram = raw.get("slope_histogram")
                if (len(raw["metrics"]) > 128 or (histogram and len(histogram["area_fraction"]) > 128)
                        or (histogram and evidence.get("comparison_scale_m") != histogram["support_scale_m"])
                        or (histogram and any(not math.isfinite(value) or not 0 <= value <= 1
                                              for value in histogram["area_fraction"]))):
                    continue
                return {"available": True, "metrics": raw["metrics"], "slope_histogram": histogram,
                        "limitations": raw.get("limitations", []),
                        "unavailable_dimensions": raw.get("unavailable_dimensions", []),
                        "evidence_id": identifier, "artifact_sha256": evidence["artifact_sha256"],
                        "receipt_id": receipt["id"], "operation_id": operation["id"]}
        except (KeyError, ValueError, TypeError, PersistenceError, OSError, ValidationError):
            continue
    return unavailable


def build_snapshot(uow: Any, blobs: Any, run_id: str, candidate_id: str) -> dict[str, Any]:
    """Only current pinned records; a foreign candidate cannot turn into a report about its neighbour."""
    run, mission, candidate, aoi = authorized_subject(uow, run_id, candidate_id)
    if candidate is None:
        raise NotFound()
    if (len(mission["requirements"]) > 128 or len(candidate.get("evidence_ids", [])) > 512
            or len(run.get("test_ids", [])) > 128 or len(run.get("test_result_ids", [])) > 128):
        raise ApiError("RESOURCE_LIMIT", "This evidence snapshot exceeds the PDF report bounds.", 422)
    rover = None
    if run.get("rover_revision_id"):
        rover = uow.require("rover_revisions", run["rover_revision_id"])
        if rover.get("workspace_id") != run["workspace_id"] or (
            run.get("rover_content_sha256") is not None
            and rover.get("content_sha256") != run["rover_content_sha256"]
        ):
            raise NotFound()
    benchmarks = site_benchmarks(uow, blobs, run_id, candidate_id)
    for row in benchmarks["requirements"]:
        qualification = scoped_record(uow, "qualifications", row["qualification_id"], run) \
            if row["qualification_id"] else {}
        row.update({key: qualification.get(key) for key in (
            "limitations", "evidence_ids", "receipt_id", "critic_status", "confidence", "evaluation_stage")})
    operations = uow.list("scientific_operations", {"run_id": run_id})
    if len(operations) > 1024:
        raise ApiError("RESOURCE_LIMIT", "This run exceeds the PDF operation-read bounds.", 422)
    target = scoped_record(uow, "target_profiles", run["target_profile_id"], run) \
        if run.get("target_profile_id") else None
    if target is not None and target.get("target") != mission["target"]:
        raise PersistenceError("SOURCE_CONTENT_INVALID", "The pinned target differs from its accepted contract.")
    snapshot: dict[str, Any] = {
        "schema_version": "site-evidence-brief.v1", "publication": "CURRENT_UNASSURED_EVIDENCE",
        "run": {key: run.get(key) for key in (
            "run_id", "workspace_id", "revision", "state", "mode", "dataset_lock_id", "config_sha256",
            "created_at", "mission_revision_id", "rover_revision_id")},
        "mission": {key: mission.get(key) for key in (
            "id", "mission_id", "revision", "content_sha256", "name", "objective", "accepted_at",
            "target", "assumptions")},
        "rover": {key: rover.get(key) for key in ("id", "revision", "name", "content_sha256")} if rover else None,
        "candidate": {key: candidate.get(key) for key in (
            "id", "name", "aoi", "origin", "discovery_method", "novelty_status", "limitations")},
        "benchmarks": benchmarks,
        "candidate_analysis": _analysis(uow, blobs, run, candidate, aoi, operations, target=False),
        "target_analysis": _analysis(uow, blobs, run, target, mission["target"], operations, target=True),
        "attempts": [], "images": [], "display_notes": [], "run_reason": None, "search_scope": None,
        "search_limitations": run.get("search_limitations", []),
        "context_note": "Operator documents and custom rover features are untrusted context, not verified constraints.",
    }
    if run.get("state") in {"FAILED", "BLOCKED"}:
        events = uow.list("run_events", {"run_id": run_id, "event_type": f"run.{run['state'].lower()}"})
        for event in sorted(events, key=lambda row: row.get("seq", 0), reverse=True):
            if (event.get("event_type") != f"run.{run['state'].lower()}" or event.get("state") != run["state"]
                    or event.get("seq", 0) > run.get("last_event_seq", 0)
                    or any(event.get(key) != run.get(key) for key in ("workspace_id", "run_id", "mode"))):
                continue
            data = event.get("payload")
            code = failure_code(event["event_type"], run["state"], data) if isinstance(data, dict) else None
            if code:
                snapshot["run_reason"] = {"code": code, "message": FAILURE_SUMMARIES[code], "seq": event["seq"]}
            break  # A newer unknown cause cannot be replaced by an earlier recognized failure.
    for operation in reversed(operations):
        if (operation.get("operation") != "SCREEN_CANDIDATES" or operation.get("status") not in {"SUCCEEDED", "LIMITED"}
                or any(operation.get(key) != run.get(key) for key in ("workspace_id", "run_id", "mode"))):
            continue
        receipt = scoped_record(uow, "tool_receipts", operation["receipt_id"], run)
        request = operation.get("request", {})
        if (receipt.get("status") == "SUCCEEDED" and receipt.get("tool_name") == "screen_earth_candidates"
                and request.get("mode") == run["mode"]
                and request.get("source_policy", {}).get("policy_id") == run.get("dataset_lock_id")
                and canonical_sha256(request) == receipt.get("input_sha256")):
            payload = ScreenCandidatesPayload.model_validate(operation.get("payload")).model_dump(mode="json")
            snapshot["search_scope"] = {key: payload.get(key) for key in (
                "search_extent", "screened_count", "stop_reason", "limitations")}
            snapshot["search_scope"].update(operation_id=operation["id"], receipt_id=receipt["id"])
            break
    own_tests = {}
    for identifier in run.get("test_ids", []):
        test = scoped_record(uow, "tests", identifier, run)
        if (test.get("candidate_id") == candidate_id and test.get("mission_revision_id") == mission["id"]
                and test.get("rover_revision_id") == run.get("rover_revision_id")):
            own_tests[identifier] = test
    for identifier in run.get("test_result_ids", []):
        result = scoped_record(uow, "test_results", identifier, run)
        if result.get("test_id") in own_tests:
            snapshot["attempts"].append({key: result.get(key) for key in (
                "id", "test_id", "outcome", "failure_category", "verified_route_sha256", "limitations",
                "evidence_ids", "metrics")})
    snapshot["test_plan"] = field_plan(uow, blobs, run, mission, candidate, rover, own_tests, operations)
    image_bytes = 0
    for selected, label in ((None, "Planetary target"), (candidate_id, "Earth location")):
        detail = site_detail(uow, blobs, run_id, selected)
        snapshot["display_notes"].append(f"{label}: {detail['availability']}. {detail['reason']}")
        if len(detail["display_layer_manifest_ids"]) > 2:
            snapshot["display_notes"].append(f"{label}: additional registered views omitted by the two-view limit.")
        for identifier in detail["display_layer_manifest_ids"][:2]:
            layer = scoped_record(uow, "display_layers", identifier, run)
            try:
                content = blobs.read_limited(layer["image_artifact_sha256"], 3 * 1024 * 1024)
            except (PersistenceError, OSError):
                snapshot["display_notes"].append(
                    f"{label}: display {identifier} exceeds inline bounds or is unavailable."
                )
                continue
            if image_bytes + len(content) > 3 * 1024 * 1024:
                snapshot["display_notes"].append(f"{label}: display {identifier} omitted: combined inline byte bound.")
                continue
            image_bytes += len(content)
            snapshot["images"].append({"subject": label, "manifest_id": identifier,
                "kind": layer["layer_kind"], "unit": layer["unit"], "support_scale_m": layer["support_scale_m"],
                "source_evidence_ids": layer["source_evidence_ids"], "attribution": layer["attribution"],
                "limitations": layer["limitations"], "legend": layer["legend"],
                "sha256": layer["image_artifact_sha256"], "png": base64.b64encode(content).decode("ascii")})
    # Digest describes the exact private snapshot, rather than any published passport manifest.
    snapshot["snapshot_sha256"] = canonical_sha256(snapshot)
    if len(json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode()) > MAX_INPUT:
        raise ApiError("RESOURCE_LIMIT", "This evidence snapshot exceeds the PDF input byte bound.", 422)
    return snapshot


def build_packet(uow: Any, blobs: Any, run_id: str) -> dict[str, Any]:
    """A bounded multi-location planning brief at one transactional run revision."""
    run, _mission, _candidate, _aoi = authorized_subject(uow, run_id)
    identifiers = run.get("candidate_ids", [])
    if not identifiers or len(identifiers) > 8:
        raise ApiError("RESOURCE_LIMIT", "The combined brief supports one to eight locations; "
                       "use individual PDFs.", 422)
    locations = [build_snapshot(uow, blobs, run_id, identifier) for identifier in identifiers]
    # Concise dossier contains charts and route vectors; registered raster images remain in individual appendices.
    for location in locations:
        location["images"] = []
        location.pop("snapshot_sha256")
        location["snapshot_sha256"] = canonical_sha256(location)
    packet = {"schema_version": "mission-test-brief.v1", "locations": locations, "run": locations[0]["run"]}
    packet["snapshot_sha256"] = canonical_sha256(packet)
    return packet


def render_pdf(snapshot: dict[str, Any]) -> bytes:
    content = json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode()
    if len(content) > MAX_INPUT:
        raise ApiError("RESOURCE_LIMIT", "The PDF input exceeds its bounded size.", 422)
    if not _render_slot.acquire(blocking=False):
        raise ApiError("RESOURCE_LIMIT", "Another evidence PDF is rendering. Retry after it finishes.", 429)
    try:
        # The renderer receives only this authorized snapshot, no credentials, DB sockets, paths or URLs to fetch.
        script = Path(__file__).resolve().parents[1] / "rendering/evidence_brief.py"
        environment = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        with tempfile.TemporaryDirectory(prefix="analogforge-evidence-pdf-") as directory:
            process = subprocess.Popen(  # noqa: S603 - fixed local interpreter/script; input is data, never code.
                [sys.executable, "-I", str(script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=environment, cwd=directory,
            )
            deadline = time.monotonic() + 15
            pending: bytes | None = content
            try:
                while True:
                    try:
                        output, _ = process.communicate(pending, timeout=0.1)
                        break
                    except subprocess.TimeoutExpired:
                        pending = None
                        if time.monotonic() >= deadline:
                            raise ApiError("TOOL_TIMEOUT", "The evidence PDF exceeded its rendering deadline.", 422) \
                                from None
                        if sys.platform == "darwin":
                            try:
                                usage = subprocess.run(  # noqa: S603 - fixed system tool and this renderer's PID.
                                    ["/bin/ps", "-o", "rss=", "-p", str(process.pid)], capture_output=True,
                                    timeout=0.5, check=False,
                                )
                                resident_kib = int(usage.stdout.strip()) if usage.stdout.strip() else 0
                            except (subprocess.TimeoutExpired, OSError, ValueError):
                                raise ApiError("RESOURCE_LIMIT", "The PDF memory bound could not be verified.", 422) \
                                    from None
                            if resident_kib > MEMORY_MIB * 1024:
                                raise ApiError("RESOURCE_LIMIT", "The PDF exceeded its memory bound.", 422) from None
            except BaseException:
                process.kill()
                process.communicate()
                raise
            if process.returncode or not output.startswith(b"%PDF-") or len(output) > MAX_OUTPUT:
                raise ApiError("RESOURCE_LIMIT", "The evidence PDF could not render within its bounds.", 422)
            return output
    finally:
        _render_slot.release()


def pdf_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
