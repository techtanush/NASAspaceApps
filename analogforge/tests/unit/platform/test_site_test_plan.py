"""A field brief cannot borrow a neighbouring, stale or corrupted route."""

from copy import deepcopy
from uuid import uuid4

import numpy as np
import pytest

from analogforge.application.site_test_plan import field_plan
from analogforge.ports.hashing import canonical_sha256
from tests.unit.platform.test_visualization_detail import json_record
from tests.unit.platform.test_visualization_detail import projection as projection
from tests.unit.science.test_routing_support import make_grid, raster_constraints


def route_case(projection, *, node_only=False):
    uow, blobs, run, mission, candidate = projection
    mission["content_sha256"] = "a" * 64
    constraints, _ = raster_constraints(make_grid(np.zeros((2, 2))), start=(0, 0), tasks=[])
    c = constraints.model_dump(mode="json")
    rover = uow.seed("rover_revisions", content_sha256="b" * 64)
    candidate["window_id"] = "window-under-test"
    c.update(mission_revision_id=mission["id"], mission_content_sha256=mission["content_sha256"],
             rover_revision_id=rover["id"], candidate_window_id=candidate["window_id"])
    c["tasks"] = [{"task_id": "survey-stop", "requirement_ids": [], "kind": "STOP",
        "location": {"node_id": "n1", "lon": -111.4, "lat": 35.6, "x_m": None, "y_m": None},
        "tolerance_m": 30, "dwell_s": 60, "incremental_energy_wh": 0, "required_capability": None,
        "evidence_origin": "USER_DESIGNATED"}]
    if node_only:
        c["tasks"][0]["location"].update(lon=None, lat=None)
    sha = canonical_sha256(c)
    route = {"schema_version": "1.0", "route_key": "fixture-route", "mode": "synthetic",
        "constraints_sha256": sha, "strategy": c["strategy"], "graph_revision": "fixture",
        "node_sequence": ["n0", "n1", "n0"], "task_events": [],
        "display_geometry": {"type": "LineString", "coordinates": [[-111.5, 35.5], [-111.4, 35.6], [-111.5, 35.5]]},
        "solver_claimed": {"distance_m": 1, "energy_conservative_wh": None, "unique_exposure_m": {}}}
    route_sha = canonical_sha256(route)
    test = uow.seed("tests", run_id=run["id"], mode="synthetic", candidate_id=candidate["id"],
        mission_revision_id=mission["id"], rover_revision_id=rover["id"], test_revision=1, attempt_number=1,
        constraints=c, constraints_sha256=sha, route_artifact_sha256=route_sha,
        assumptions=["Procedural fixture; not a field instruction"])
    payload = {"operation": "VERIFY_ROUTE", "outcome": "PASS", "failure_category": None,
        "search_status": "FOUND", "verified_route_sha256": route_sha, "metrics": [], "violations": [],
        "benchmark_rows": [{"constraint_id": "slope", "requirement_id": None, "rule": "<= 18 deg",
            "measured": 3, "threshold": 18, "unit": "deg", "margin": 15, "status": "PASS"}],
        "telemetry_artifact_key": None, "verification_evidence": {"local_key": "verification", "evidence_id": None},
        "limitations": ["Fixture scope"]}
    evidence = json_record(uow, blobs, run, payload, kind="VERIFICATION", body="EARTH", algorithm_id="verify-route")
    registered = {**deepcopy(payload), "verification_evidence": {"local_key": None, "evidence_id": evidence["id"]}}
    result = uow.seed("test_results", run_id=run["id"], mode="synthetic", test_id=test["id"],
        outcome="PASS", verified_route_sha256=route_sha, metrics=[], evidence_ids=[evidence["id"]])
    request = {"operation": "VERIFY_ROUTE", "mode": "synthetic", "source_policy": {"policy_id": run["dataset_lock_id"]},
        "inputs": {"operation": "VERIFY_ROUTE", "constraints": c, "constraints_sha256": sha,
                   "route": route, "route_sha256": route_sha, "search_status": "FOUND"}}
    invocation = uow.seed("invocations", run_id=run["id"], mode="synthetic", status="SUCCEEDED",
        task_kind="VERIFY_ROUTE", candidate_id=candidate["id"], input_hash=canonical_sha256(request))
    receipt = uow.seed("tool_receipts", run_id=run["id"], mode="synthetic", status="SUCCEEDED",
        invocation_id=invocation["id"], input_sha256=canonical_sha256(request), evidence_ids=[evidence["id"]])
    operation = uow.seed("scientific_operations", run_id=run["id"], mode="synthetic", operation="VERIFY_ROUTE",
        status="SUCCEEDED", request=request, receipt_id=receipt["id"], payload=registered,
        evidence_ids=[evidence["id"]])
    run.update(test_ids=[test["id"]], test_result_ids=[result["id"]], rover_revision_id=rover["id"])
    return rover, test, result, operation, receipt, invocation, evidence


def plan(projection, data):
    uow, blobs, run, mission, candidate = projection
    rover, test, *_ = data
    return field_plan(uow, blobs, run, mission, candidate, rover,
                      {row["id"]: row for row in uow.list("tests")}, uow.list("scientific_operations"))


def test_same_site_route_loop_checkpoints_and_original_assumptions_remain_readonly(projection):
    data = route_case(projection)
    before = deepcopy(projection[0].rows)
    result = plan(projection, data)
    assert result["route"]["start"] == result["route"]["finish"] == [-111.5, 35.5]
    assert result["route"]["checkpoints"][0]["position"] == [-111.4, 35.6]
    assert result["route"]["checkpoints"][0]["requirement_ids"] == []
    assert result["route"]["assumptions"] == ["Procedural fixture; not a field instruction"]
    assert "not a surveyed" in result["route_note"]
    assert before == projection[0].rows


def test_projected_task_uses_its_own_executable_route_node_for_display(projection):
    result = plan(projection, route_case(projection, node_only=True))
    assert result["route"]["checkpoints"][0]["position"] == [-111.4, 35.6]


@pytest.mark.parametrize("defect", ["candidate", "mission", "rover", "constraints", "receipt", "invocation",
                                  "evidence", "blob", "mode", "newer", "result", "payload", "outside"])
def test_unbound_routes_never_become_field_endpoints(projection, defect):
    data = route_case(projection)
    rover, test, result, operation, receipt, invocation, evidence = data
    if defect in {"candidate", "mission", "rover"}:
        key = {"candidate": "candidate_id", "mission": "mission_revision_id", "rover": "rover_revision_id"}[defect]
        test[key] = str(uuid4())
    elif defect == "constraints":
        test["constraints_sha256"] = "0" * 64
    elif defect == "receipt":
        receipt["input_sha256"] = "0" * 64
    elif defect == "invocation":
        invocation["candidate_id"] = str(uuid4())
    elif defect == "evidence":
        evidence["body"] = "MARS"
    elif defect == "blob":
        projection[1].path(evidence["artifact_sha256"]).write_bytes(b"{}")
    elif defect == "mode":
        operation["mode"] = "live"
    elif defect == "newer":
        projection[0].seed("tests", **{**test, "id": str(uuid4()), "attempt_number": 2,
                                     "route_artifact_sha256": None})
    elif defect == "result":
        result["verified_route_sha256"] = "0" * 64
    elif defect == "payload":
        operation["payload"]["benchmark_rows"][0]["measured"] = 4
    else:
        projection[-1]["aoi"]["bbox"] = [-110, 35, -109, 36]
    assert plan(projection, data)["route"] is None
