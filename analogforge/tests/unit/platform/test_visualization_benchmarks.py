"""Benchmarks preserve accepted criteria, committed failures, units and attempt ancestry."""

from copy import deepcopy
from uuid import uuid4

import pytest

from analogforge.application.visualization_benchmarks import site_benchmarks
from analogforge.db.store import NotFound, PersistenceError
from analogforge.ports.hashing import canonical_json_bytes
from tests.unit.platform.test_visualization_detail import json_record, source_record
from tests.unit.platform.test_visualization_detail import projection as projection


def add_comparison(projection, status="PASS", value=0.08):
    uow, blobs, run, mission, candidate = projection
    requirement = mission["requirements"][0]
    source = source_record(uow, run, candidate)
    accepted = json_record(
        uow, blobs, run, requirement, body="EARTH", kind="ASSUMPTION", algorithm_id="accepted-requirement-record"
    )
    payload = {
        "operation": "COMPARE_REQUIREMENT",
        "requirement_id": requirement["id"],
        "proposed_status": status,
        "reason_code": "MEETS_CRITERION",
        "evaluation_stage": "PRELIMINARY",
        "confidence": "MEDIUM",
        "comparison_scale_m": 30,
        "measured_value": value,
        "measured_unit": requirement["unit"],
        "threshold_lower": requirement["lower"],
        "threshold_upper": requirement["upper"],
        "covered_subcriteria": [],
        "uncovered_subcriteria": [],
        "explanation": "Recorded deterministic comparison",
        "limitations": [],
        "comparison_evidence": {"local_key": "comparison", "evidence_id": None},
        "adequacy": {
            "observable_policy_id": "slope-band-area-fraction-v1",
            "policy_sha256": "1" * 64,
            "gates": [],
            "validation_level": "S3",
        },
    }
    comparison = json_record(
        uow,
        blobs,
        run,
        payload,
        body="EARTH",
        kind="COMPARISON",
        algorithm_id="compare-requirement",
        comparison_scale_m=30,
    )
    comparison["input_evidence_ids"] = [source["id"], accepted["id"]]
    receipt = uow.seed(
        "tool_receipts",
        run_id=run["id"],
        mode=run["mode"],
        status="SUCCEEDED",
        tool_name="compare_requirement",
        evidence_ids=[comparison["id"], accepted["id"]],
    )
    payload = deepcopy(payload)
    payload["comparison_evidence"] = {"local_key": None, "evidence_id": comparison["id"]}
    row = uow.seed(
        "qualifications",
        run_id=run["id"],
        mode=run["mode"],
        created_at="2026-11-14T00:00:00Z",
        schema_version="1.0",
        candidate_id=candidate["id"],
        requirement_id=requirement["id"],
        status=status,
        evidence_ids=receipt["evidence_ids"],
        rule_id="slope-band-area-fraction-v1",
        rule_version="1.0",
        confidence="MEDIUM",
        comparison_scale_m=30,
        explanation=payload["explanation"],
        limitations=[],
        critic_status="UNREVIEWED",
        critique_evidence_ids=[],
        payload=payload,
        receipt_id=receipt["id"],
    )
    run["qualification_ids"].append(row["id"])
    return row, comparison, receipt, accepted


def test_verbatim_criteria_committed_failure_and_numeric_precision(projection):
    uow, blobs, run, mission, candidate = projection
    row, comparison, receipt, _ = add_comparison(projection, "FAIL", 0.0001234567890123)
    before = deepcopy(uow.rows)
    result = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    benchmark = result["requirements"][0]
    assert benchmark["requirement"] == mission["requirements"][0]
    assert benchmark["status"] == "FAIL" and benchmark["qualification_id"] == row["id"]
    assert benchmark["measurement"] == {
        "value": 0.0001234567890123,
        "unit": "fraction",
        "support_scale_m": 30,
        "comparison_evidence_id": comparison["id"],
        "receipt_id": receipt["id"],
        "reason": "Exact registered comparison value; no margin, score or new measurement was calculated.",
    }
    assert result["dataset_lock_id"] == run["dataset_lock_id"]
    assert result["test_result_ids"] == [] and uow.rows == before


@pytest.mark.parametrize("status,value", [("UNKNOWN", None), ("GAP", None), ("FAIL", None)])
def test_unknown_gap_and_missing_values_are_never_zero(projection, status, value):
    uow, blobs, run, _, candidate = projection
    add_comparison(projection, status, value)
    row = site_benchmarks(uow, blobs, run["id"], candidate["id"])["requirements"][0]
    assert row["status"] == status
    assert row["measurement"]["value"] is None
    assert row["measurement"]["support_scale_m"] is None


def test_zero_is_an_actual_value_not_missing(projection):
    uow, blobs, run, _, candidate = projection
    add_comparison(projection, "FAIL", 0)
    assert site_benchmarks(uow, blobs, run["id"], candidate["id"])["requirements"][0]["measurement"]["value"] == 0


def test_final_terrain_measurement_does_not_require_a_rover_attempt(projection):
    uow, blobs, run, _, candidate = projection
    row, comparison, _, _ = add_comparison(projection)
    row["payload"]["evaluation_stage"] = "FINAL"
    raw = deepcopy(row["payload"])
    raw["comparison_evidence"] = {"local_key": "comparison", "evidence_id": None}
    blob = blobs.put_bytes(canonical_json_bytes(raw), "application/json")
    uow.seed("artifacts", sha256=blob.sha256, media_type="application/json", run_id=run["id"])
    comparison["artifact_sha256"] = blob.sha256
    result = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert result["requirements"][0]["measurement"]["value"] == 0.08
    assert result["requirements"][0]["test_result_ids"] == []


def test_route_numeric_measurement_requires_actual_committed_candidate_attempt(projection):
    uow, blobs, run, mission, candidate = projection
    mission["requirements"][0]["observable"] = "unique_slope_exposure_m"
    add_comparison(projection)
    result = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert result["requirements"][0]["measurement"]["value"] is None


@pytest.mark.parametrize("mutation", ["unit", "support", "zero_support", "policy"])
def test_internally_consistent_artifact_still_requires_accepted_units_support_and_policy(projection, mutation):
    uow, blobs, run, _, candidate = projection
    row, comparison, _, _ = add_comparison(projection)
    if mutation == "unit":
        row["payload"]["measured_unit"] = "deg"
    elif mutation in {"support", "zero_support"}:
        support = 500 if mutation == "support" else 0
        row["payload"]["comparison_scale_m"] = support
        row["comparison_scale_m"] = support
        comparison["comparison_scale_m"] = support
    else:
        row["payload"]["adequacy"]["observable_policy_id"] = "a-different-policy"
    raw = deepcopy(row["payload"])
    raw["comparison_evidence"] = {"local_key": "comparison", "evidence_id": None}
    blob = blobs.put_bytes(canonical_json_bytes(raw), "application/json")
    uow.seed("artifacts", sha256=blob.sha256, media_type="application/json", run_id=run["id"])
    comparison["artifact_sha256"] = blob.sha256
    result = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert result["requirements"][0]["measurement"]["value"] is None


def test_only_pinned_current_rows_in_accepted_requirement_order(projection):
    uow, blobs, run, mission, candidate = projection
    row, _, _, _ = add_comparison(projection)
    old = deepcopy(row)
    old.update(id=str(uuid4()), status="FAIL")
    uow.seed("qualifications", **old)
    missing = deepcopy(mission["requirements"][0])
    missing["id"] = "R-UNCOMPUTED"
    mission["requirements"].insert(0, missing)
    result = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert [r["requirement"]["id"] for r in result["requirements"]] == ["R-UNCOMPUTED", row["requirement_id"]]
    assert result["requirements"][0]["status"] == "UNKNOWN"
    assert result["requirements"][0]["qualification_id"] is None
    assert result["requirements"][1]["status"] == "PASS"


@pytest.mark.parametrize(
    "mutation",
    [
        "unit",
        "support",
        "threshold",
        "unregistered",
        "failed_receipt",
        "foreign_receipt",
        "source",
        "wrong_body",
        "accepted",
        "tampered",
        "missing",
    ],
)
def test_incompatible_or_unregistered_numbers_remain_unknown(projection, mutation):
    uow, blobs, run, _, candidate = projection
    row, comparison, receipt, accepted = add_comparison(projection)
    if mutation == "unit":
        row["payload"]["measured_unit"] = "deg"
    elif mutation == "support":
        row["payload"]["comparison_scale_m"] = 500
    elif mutation == "threshold":
        row["payload"]["threshold_lower"] = 0
    elif mutation == "unregistered":
        receipt["evidence_ids"] = []
    elif mutation == "failed_receipt":
        receipt["status"] = "FAILED"
    elif mutation == "foreign_receipt":
        receipt["run_id"] = str(uuid4())
    elif mutation == "source":
        candidate["analysis_payload"] = None
    elif mutation == "wrong_body":
        comparison["body"] = "MARS"
    elif mutation == "accepted":
        comparison["input_evidence_ids"].remove(accepted["id"])
    elif mutation == "tampered":
        blobs.path(comparison["artifact_sha256"]).write_bytes(b"different value")
    else:
        blobs.path(comparison["artifact_sha256"]).unlink()
    projected = site_benchmarks(uow, blobs, run["id"], candidate["id"])["requirements"][0]
    assert projected["status"] == row["status"]  # Preserve the actual committed fact.
    assert projected["measurement"]["value"] is None


def add_attempt(projection, comparison, *, foreign=False):
    uow, _, run, _, candidate = projection
    evidence = uow.seed(
        "evidence",
        run_id=run["id"],
        mode=run["mode"],
        kind="VERIFICATION",
        body="EARTH",
        algorithm_id="verify-route",
        input_evidence_ids=[],
    )
    comparison["input_evidence_ids"].append(evidence["id"])
    test = uow.seed(
        "tests",
        run_id=run["id"],
        mode=run["mode"],
        mission_revision_id=run["mission_revision_id"],
        candidate_id=str(uuid4()) if foreign else candidate["id"],
        attempt_number=2,
        test_revision=2,
    )
    result = uow.seed(
        "test_results", run_id=run["id"], mode=run["mode"], test_id=test["id"], evidence_ids=[evidence["id"]]
    )
    run["test_ids"].append(test["id"])
    run["test_result_ids"].append(result["id"])
    return test, result


def test_only_actual_candidate_attempt_results_are_attached(projection):
    uow, blobs, run, _, candidate = projection
    _, comparison, _, _ = add_comparison(projection)
    _, result = add_attempt(projection, comparison)
    response = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert response["test_result_ids"] == [result["id"]]
    assert response["requirements"][0]["test_result_ids"] == [result["id"]]
    assert response["requirements"][0]["measurement"]["value"] == 0.08


@pytest.mark.parametrize("mutation", ["different_candidate", "unpin_test", "unpin_result", "different_mission"])
def test_foreign_or_uncommitted_attempt_is_not_borrowed(projection, mutation):
    uow, blobs, run, _, candidate = projection
    _, comparison, _, _ = add_comparison(projection)
    test, _ = add_attempt(projection, comparison, foreign=mutation == "different_candidate")
    if mutation == "unpin_test":
        run["test_ids"] = []
    elif mutation == "unpin_result":
        run["test_result_ids"] = []
    elif mutation == "different_mission":
        test["mission_revision_id"] = str(uuid4())
    response = site_benchmarks(uow, blobs, run["id"], candidate["id"])
    assert response["test_result_ids"] == []
    assert response["requirements"][0]["test_result_ids"] == []
    assert response["requirements"][0]["measurement"]["value"] is None


def test_conflicting_pinned_qualifications_fail_instead_of_guessing(projection):
    uow, blobs, run, _, candidate = projection
    row, _, _, _ = add_comparison(projection)
    duplicate = deepcopy(row)
    duplicate["id"] = str(uuid4())
    uow.seed("qualifications", **duplicate)
    run["qualification_ids"].append(duplicate["id"])
    with pytest.raises(PersistenceError):
        site_benchmarks(uow, blobs, run["id"], candidate["id"])


def test_known_candidate_from_different_run_is_rejected(projection):
    uow, blobs, run, _, candidate = projection
    candidate["run_id"] = str(uuid4())
    with pytest.raises(NotFound):
        site_benchmarks(uow, blobs, run["id"], candidate["id"])
