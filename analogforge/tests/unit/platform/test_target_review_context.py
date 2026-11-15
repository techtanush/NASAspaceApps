"""Target review sees registered lineage and availability without invented qualification."""

from copy import deepcopy

import pytest

from analogforge.agents.runtime.scripted_provider import project_payload
from analogforge.agents.runtime.target_projection import target_coordinate_context, target_evidence_context


def target_facts():
    return {
        "mission": {"requirements": [{"id": "terrain-1", "dimension": "TERRAIN"},
                                     {"id": "mineral-2", "dimension": "SCIENCE"},
                                     {"id": "power-3", "dimension": "POWER"}]},
        "target_measurement_spec_id": "registered-target-spec",
        "target": {"target": {"body": "MARS"}, "evidence_ids": ["profile", "grid", "source"],
                   "payload": {"slope_histogram": {"valid_area_m2": 100}, "unavailable_dimensions": [
                       {"dimension": "SCIENCE", "reason_code": "NO_COVERAGE", "message": "No mineral dataset."}]}},
        "evidence_records": [
            {"id": "profile", "kind": "DERIVED", "body": "MARS", "input_evidence_ids": ["grid"]},
            {"id": "grid", "kind": "DERIVED", "body": "MARS", "input_evidence_ids": ["source"]},
            {"id": "source", "kind": "SOURCE", "body": "MARS", "input_evidence_ids": ["parent"]},
            {"id": "parent", "kind": "SOURCE", "body": "MARS", "input_evidence_ids": []},
            {"id": "earth", "kind": "SOURCE", "body": "EARTH", "input_evidence_ids": []},
            {"id": "unrelated", "kind": "SOURCE", "body": "MARS", "input_evidence_ids": []},
        ],
    }


def test_lineage_selects_only_registered_target_sources_and_derived_measurements():
    facts = target_facts()
    original = deepcopy(facts)
    result = target_evidence_context(facts)
    assert result["source_evidence_ids"] == ["parent", "source"]
    assert result["measurement_evidence_ids"] == ["profile", "grid"]
    terrain, mineral, power = result["dimension_evidence"]
    assert terrain["requirement_id"] == "terrain-1" and terrain["availability"] == "AVAILABLE"
    assert terrain["evidence_ids"] == ["profile", "grid"]
    assert terrain["measurement_spec_id"] == "registered-target-spec"
    assert "downstream" in terrain["limitation"]
    assert mineral["availability"] == "NO_COVERAGE" and mineral["evidence_ids"] == []
    assert mineral["limitation"] == "No mineral dataset."
    assert power["availability"] == "UNRESOLVED" and power["measurement_spec_id"] is None
    assert facts == original


def test_empty_or_unregistered_evidence_and_invalid_coverage_remain_unresolved():
    for change in ("unregistered", "empty_area", "no_source", "no_target"):
        facts = target_facts()
        if change == "unregistered":
            facts["evidence_records"] = []
        elif change == "empty_area":
            facts["target"]["payload"]["slope_histogram"]["valid_area_m2"] = 0
        elif change == "no_source":
            facts["evidence_records"] = [row for row in facts["evidence_records"] if row["kind"] != "SOURCE"]
        else:
            facts["target"] = None
        result = target_evidence_context(facts)
        terrain = result["dimension_evidence"][0]
        assert terrain["availability"] == "UNRESOLVED"
        assert terrain["evidence_ids"] == [] and terrain["measurement_spec_id"] is None


def test_unknown_parent_cycles_cannot_add_foreign_or_unregistered_sources():
    facts = target_facts()
    facts["evidence_records"][0]["input_evidence_ids"] += ["missing", "earth"]
    facts["evidence_records"][3]["input_evidence_ids"] = ["profile"]
    assert target_evidence_context(facts)["source_evidence_ids"] == ["parent", "source"]


@pytest.mark.parametrize("geometry", [True, False])
def test_rover_presence_and_proposal_provenance_cannot_relabel_registered_target_facts(geometry):
    facts = coordinate_facts()
    facts["mission"].update(id="accepted-contract", accepted_at="2026-11-15T00:00:00Z")
    for row in facts["mission"]["requirements"]:
        row.update(origin="PROPOSED_DEFAULT", acceptance_note="Proposed threshold requires explicit user review")
    if not geometry:
        facts["registered_receipts"][0]["tool_name"] = "inspect_contract"
    facts.update(validation_receipt_id="contract-only", target_coordinate_context=target_coordinate_context(facts))
    without_rover = project_payload("planetary_target", facts)
    facts["rover"] = {"max_slope_deg": 18, "ground_clearance_m": 0.2, "energy_model": None}
    before = deepcopy(facts)
    with_rover = project_payload("planetary_target", facts)
    assert with_rover == without_rover and facts == before
    assert with_rover["comparison_ready"] is geometry
    assert [row["availability"] for row in with_rover["dimension_evidence"]] == [
        "AVAILABLE", "NO_COVERAGE", "UNRESOLVED",
    ]
    assert with_rover["source_evidence_ids"] == ["parent", "source"]


def coordinate_facts():
    facts = target_facts()
    scope = {"workspace_id": "workspace", "run_id": "run", "mode": "live"}
    target = {"body": "MARS", "bbox": [1, 2, 3, 4], "crs_wkt": None, "vertical_datum": "Unknown"}
    facts["target"].update(**scope, id="registered-profile", target=target)
    facts["registered_receipts"] = [
        {**scope, "id": "geometry", "tool_name": "characterize_target", "status": "SUCCEEDED",
         "evidence_ids": ["profile", "grid", "source"]},
        {**scope, "id": "ingest", "tool_name": "fetch_dataset", "status": "SUCCEEDED",
         "evidence_ids": ["ingest-source"]},
    ]
    facts["target_operations"] = [{**scope, "operation": "CHARACTERIZE_TARGET", "receipt_id": "geometry",
        "status": "SUCCEEDED", "evidence_ids": ["profile", "grid", "source"], "request": {"inputs": {
            "target": deepcopy(target), "source": {"kind": "LOCAL_DATASET", "dataset_id": "mars-terrain"}}}}]
    facts["source_ingest_operations"] = [{**scope, "operation": "INGEST_LOCAL_DATASET", "receipt_id": "ingest",
        "status": "SUCCEEDED", "evidence_ids": ["ingest-source"], "request": {"inputs": {"manifest": {
            "dataset_id": "mars-terrain", "body": "MARS", "crs": {"wkt": "registered-source-wkt"},
            "vertical_reference": "Declared areoid", "units": "m", "quantity": "ELEVATION"}}}}]
    return facts


def test_coordinate_context_uses_real_geometry_and_ingestion_receipts_and_keeps_operator_aoi_unchanged():
    facts = coordinate_facts()
    before = deepcopy(facts)
    result = target_coordinate_context(facts)
    assert result["geometry_validation_receipt_id"] == "geometry"
    assert result["geometry_validation_operation"] == "CHARACTERIZE_TARGET"
    assert result["source_frames"][0]["vertical_reference"] == "Declared areoid"
    assert result["source_frames"][0]["ingestion_receipt_id"] == "ingest"
    assert len(result["source_frames"][0]["manifest_sha256"]) == 64
    result["source_frames"][0]["crs"]["wkt"] = "changed"
    assert facts == before and facts["target"]["target"]["crs_wkt"] is None


@pytest.mark.parametrize("defect", ["contract_receipt", "foreign_run", "foreign_mode", "wrong_aoi", "missing_scope"])
def test_missing_or_foreign_geometry_validation_does_not_become_readiness(defect):
    facts = coordinate_facts()
    if defect == "contract_receipt":
        facts["registered_receipts"][0]["tool_name"] = "inspect_contract"
    elif defect == "foreign_run":
        facts["target_operations"][0]["run_id"] = "another-run"
    elif defect == "foreign_mode":
        facts["registered_receipts"][0]["mode"] = "synthetic"
    elif defect == "wrong_aoi":
        facts["target_operations"][0]["request"]["inputs"]["target"]["bbox"] = [5, 6, 7, 8]
    else:
        facts["target"].pop("workspace_id")
    result = target_coordinate_context(facts)
    assert result["geometry_validation_receipt_id"] is None and result["source_frames"] == []
    facts.update(target_coordinate_context=result, validation_receipt_id="contract-only")
    facts["mission"]["id"] = "accepted-contract"
    payload = project_payload("planetary_target", facts)
    assert payload["geometry_validation_receipt_id"] is None and payload["comparison_ready"] is False


@pytest.mark.parametrize("defect", ["dataset", "body", "receipt_scope", "failed", "evidence"])
def test_unrelated_or_failed_ingestion_cannot_supply_a_target_source_frame(defect):
    facts = coordinate_facts()
    operation = facts["source_ingest_operations"][0]
    if defect == "dataset":
        operation["request"]["inputs"]["manifest"]["dataset_id"] = "another-dataset"
    elif defect == "body":
        operation["request"]["inputs"]["manifest"]["body"] = "EARTH"
    elif defect == "receipt_scope":
        facts["registered_receipts"][1]["workspace_id"] = "another-workspace"
    elif defect == "failed":
        operation["status"] = "FAILED"
    else:
        facts["registered_receipts"][1]["evidence_ids"] = ["foreign-source"]
    result = target_coordinate_context(facts)
    assert result["geometry_validation_receipt_id"] == "geometry"
    assert result["source_frames"] == []
