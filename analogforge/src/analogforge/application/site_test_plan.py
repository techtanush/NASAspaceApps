"""Read-only field-planning presentation. Never designs a route or qualifies hardware."""

from typing import Any

from analogforge.application.field_guidance import field_guidance
from analogforge.application.visualization_detail import registered_json, scoped_record
from analogforge.db.store import PersistenceError
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import VerifyRouteInput, VerifyRoutePayload


def field_plan(
    uow: Any, blobs: Any, run: dict[str, Any], mission: dict[str, Any],
    candidate: dict[str, Any], rover: dict[str, Any] | None, tests: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Only the latest site's experiment can supply a geographic planning reference."""
    west, south, east, north = candidate["aoi"]["bbox"]
    plan: dict[str, Any] = {
        "candidate_id": candidate["id"], "center": [(west + east) / 2, (south + north) / 2],
        "bbox": candidate["aoi"]["bbox"], "route": None,
        "route_note": "Route not yet computed for this location. The region centre is a reference, not a start point.",
        "field_readiness": "Survey and operator approval required; no physical field trial has been recorded.",
        "tests": [{"requirement_id": row["id"], "label": row["label"], **field_guidance(row)}
                  for row in mission.get("requirements", [])],
        "steps": [
            "Confirm land access, permits, environmental restrictions and a site-specific operating safety plan.",
            "Survey the region at rover scale. Locate obstacles, loose ground, slope transitions and recovery access; "
            "regional raster cells do not resolve these hazards.",
            "Confirm a start, checkpoints and finish on the ground. Re-plan and verify any changes before driving.",
            "Record timestamped position, distance, slope, speed, wheel slip, battery use and task outcomes. "
            "Keep instrument calibration and uncertainty with the observations.",
            "Compare each observation with its accepted criterion in the stated units and support. "
            "Record unmet or unmeasured criteria; do not convert a terrain match into a hardware PASS.",
        ],
    }
    if not tests or rover is None:
        return plan
    test = max(tests.values(), key=lambda row: (
        row.get("attempt_number", row.get("test_revision", 1)), row.get("created_at", ""), row["id"]))
    plan["route_note"] = "The latest site experiment has no compatible registered geographic route. " \
        "Compute and verify a route before selecting field endpoints."
    try:
        constraints = test["constraints"]
        route_sha = test.get("route_artifact_sha256")
        expected = {"mode": run["mode"], "mission_revision_id": mission["id"],
                    "mission_content_sha256": mission["content_sha256"], "rover_revision_id": rover["id"],
                    "rover_content_sha256": rover["content_sha256"],
                    "candidate_window_id": candidate["window_id"], "test_revision": test["test_revision"]}
        if (test.get("candidate_id") != candidate["id"]
                or test.get("mission_revision_id") != mission["id"] or test.get("rover_revision_id") != rover["id"]
                or not route_sha or canonical_sha256(constraints) != test["constraints_sha256"]
                or any(constraints.get(key) != value for key, value in expected.items())):
            return plan
        results = [scoped_record(uow, "test_results", identifier, run)
                   for identifier in run.get("test_result_ids", [])]
        results = [row for row in results if row.get("test_id") == test["id"]]
        if len(results) != 1:
            return plan
        result = results[0]
        if result.get("verified_route_sha256") != route_sha:
            return plan
        for operation in reversed(operations):
            if (operation.get("operation") != "VERIFY_ROUTE"
                    or operation.get("status") not in {"SUCCEEDED", "LIMITED"}
                    or any(operation.get(key) != run.get(key) for key in ("workspace_id", "run_id", "mode"))):
                continue
            request = operation["request"]
            source = VerifyRouteInput.model_validate(request["inputs"])
            if (source.constraints.artifact_kind != "RASTER_ROUTE_TEST" or source.constraints.grid is None
                    or request.get("operation") != "VERIFY_ROUTE" or request.get("mode") != run["mode"]
                    or request.get("source_policy", {}).get("policy_id") != run.get("dataset_lock_id")
                    or source.constraints.model_dump(mode="json") != constraints
                    or source.constraints_sha256 != test["constraints_sha256"]
                    or source.route.constraints_sha256 != test["constraints_sha256"]
                    or source.route.mode != run["mode"]
                    or source.route_sha256 != route_sha or canonical_sha256(source.route) != route_sha):
                continue
            receipt = scoped_record(uow, "tool_receipts", operation["receipt_id"], run)
            invocation = scoped_record(uow, "invocations", receipt["invocation_id"], run)
            if (receipt.get("status") != "SUCCEEDED" or receipt.get("input_sha256") != canonical_sha256(request)
                    or invocation.get("status") != "SUCCEEDED" or invocation.get("task_kind") != "VERIFY_ROUTE"
                    or invocation.get("candidate_id") != candidate["id"]
                    or invocation.get("input_hash") != canonical_sha256(request)):
                continue
            verified = False
            for identifier in set(result.get("evidence_ids", [])) & set(operation.get("evidence_ids", [])):
                evidence = scoped_record(uow, "evidence", identifier, run)
                if (identifier not in receipt.get("evidence_ids", []) or evidence.get("kind") != "VERIFICATION"
                        or evidence.get("algorithm_id") != "verify-route" or evidence.get("body") != "EARTH"):
                    continue
                payload = VerifyRoutePayload.model_validate(registered_json(uow, blobs, evidence, run))
                registered = VerifyRoutePayload.model_validate(operation.get("payload"))
                if (payload.model_dump(mode="json", exclude={"verification_evidence"})
                        == registered.model_dump(mode="json", exclude={"verification_evidence"})
                        and str(registered.verification_evidence.evidence_id) == identifier
                        and payload.verified_route_sha256 == route_sha and payload.outcome == result["outcome"]
                        and [m.model_dump(mode="json") for m in payload.metrics] == result.get("metrics", [])):
                    verified = True
                    break
            geometry = source.route.display_geometry
            if (not verified or geometry is None or len(geometry.coordinates) > 2048
                    or len(source.constraints.tasks) > 64):
                continue
            points = [list(point) for point in geometry.coordinates]
            if not all(west <= lon <= east and south <= lat <= north for lon, lat in points):
                continue
            checkpoints = []
            for task in source.constraints.tasks:
                location = task.location
                point = None
                if location.lon is not None and location.lat is not None:
                    point = [location.lon, location.lat]
                elif len(points) == len(source.route.node_sequence):
                    node = next((event.node_id for event in source.route.task_events
                                 if event.task_id == task.task_id), location.node_id)
                    if node in source.route.node_sequence:
                        point = points[source.route.node_sequence.index(node)]
                if point is not None:
                    if not (west <= point[0] <= east and south <= point[1] <= north):
                        return plan
                    checkpoints.append({"id": task.task_id, "position": point,
                        "activity": task.kind, "capability": task.required_capability,
                        "requirement_ids": task.requirement_ids, "dwell_s": task.dwell_s,
                        "tolerance_m": task.tolerance_m, "origin": task.evidence_origin})
            plan["route"] = {"test_id": test["id"], "result_id": result["id"], "outcome": result["outcome"],
                "sha256": route_sha, "start": points[0], "finish": points[-1], "coordinates": points,
                "checkpoints": checkpoints, "metrics": result.get("metrics", []),
                "benchmark_rows": payload.benchmark_rows,
                "support_scale_m": source.constraints.grid.cell_size_m if source.constraints.grid else None,
                "assumptions": test.get("assumptions", []), "limitations": result.get("limitations", [])}
            # JSON projection, including frozen verifier rows, remains plain data.
            plan["route"]["benchmark_rows"] = [row.model_dump(mode="json") for row in payload.benchmark_rows]
            plan["route_note"] = ("Computed raster route: a planning reference, not a surveyed or cleared "
                                  "driving corridor. Checkpoints and design defaults retain recorded assumptions.")
            break
    except (KeyError, ValueError, TypeError, PersistenceError, OSError):
        return plan
    return plan
