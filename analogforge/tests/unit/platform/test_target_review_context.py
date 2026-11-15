"""Target review sees registered lineage and availability without invented qualification."""

from copy import deepcopy

from analogforge.agents.runtime.target_projection import target_evidence_context


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
