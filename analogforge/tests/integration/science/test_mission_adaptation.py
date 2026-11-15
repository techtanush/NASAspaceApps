"""Mission sensitivity through real synthetic rasters and the science facade.

These are bounded fixture-domain checks, not claims about NASA site optimality. The Earth
source bytes stay identical across each paired comparison; only the declared inputs change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from support.builders import load_mission, make_context, requirement
from support.practice import (
    Flow,
    analyze,
    candidate_ref,
    characterize_mars,
    compare,
    local,
    make_practice_context,
    service,
)

from analogforge.ports import catalog
from analogforge.ports.domain_models import Requirement
from analogforge.ports.science_payloads import (
    CharacterizeTargetPayload,
    CompareRequirementPayload,
    OptimizePortfolioInput,
    OptimizePortfolioPayload,
    QualificationRowInput,
    ScreenCandidatesInput,
    ScreenCandidatesPayload,
)
from analogforge.science.fixtures.practice import generate_all

EARTH = "practice-earth-grid-v1"
MARS = "practice-mars-target-v1"
FLAT, RAMP = "grid-r0c0", "grid-r0c1"


def source_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def band_req(rid: str, band: list[float], lower: float, weight: float = 1.0) -> Requirement:
    template = requirement(load_mission("mission-mars-mobility"), "R-SLOPE-AVAILABILITY")
    raw = template.model_dump(mode="json")
    raw.update(
        id=rid,
        label=rid,
        lower=lower,
        upper=None,
        weight=weight,
        minimum_support_scale_m=60,
        maximum_support_scale_m=60,
    )
    raw["parameters"].update(slope_band_deg=band, co_location_group=None)
    return Requirement.model_validate(raw)


def screened(
    flow: Flow, reqs: list[Requirement], target: CharacterizeTargetPayload | None = None, cap: int = 1
) -> ScreenCandidatesPayload:
    result, _ = flow.call(
        ScreenCandidatesInput(
            # Generated grid has no reserved negative-control slot, so cap=1 tests the scientific advice.
            search_region_set_id="local-dataset-grid-v1",
            source=local(EARTH),
            target_metrics=target.metrics if target else [],
            target_histogram=target.slope_histogram if target else None,
            requirements=reqs,
            max_detailed=cap,
            reference_set_id=catalog.REFERENCE_SET_PRACTICE,
        ),
        datasets=[EARTH],
    )
    assert isinstance(result.payload, ScreenCandidatesPayload), result.issues
    return result.payload


def test_changed_target_measurement_changes_w1_order_without_changing_earth_source(tmp_path: Path) -> None:
    shared = make_practice_context(tmp_path / "shared")
    earth_root = shared.dataset_roots[EARTH]
    original = source_hashes(earth_root)
    req = band_req("TARGET-W1", [0, 5], 0.8)
    req = req.model_copy(
        update={
            "observable": "slope_distribution_w1_deg",
            "operator": "LTE",
            "lower": None,
            "upper": 5.0,
            "unit": "deg",
            "minimum_support_scale_m": 480.0,
            "maximum_support_scale_m": 480.0,
            "parameters": req.parameters.model_copy(update={"slope_band_deg": None}),
        }
    )
    outcomes: dict[str, ScreenCandidatesPayload] = {}
    histograms: dict[str, list[float]] = {}
    for label, degrees in (("flat-target", 0.0), ("steep-target", 18.0)):
        target_root = tmp_path / label
        generate_all(target_root, only=[MARS], target_fractions=((degrees, 1.0),))
        roots = {**shared.dataset_roots, MARS: target_root / MARS}
        assert roots[EARTH] == earth_root
        flow = Flow(service(), make_context(tmp_path / f"scratch-{label}", dataset_roots=roots))
        target, _ = characterize_mars(flow)
        assert target.slope_histogram is not None
        histograms[label] = list(target.slope_histogram.area_fraction)
        advice = screened(flow, [req], target)
        outcomes[label] = advice
        values = {w.window_id: w.feature_scores["slope_w1_deg"] for w in advice.windows if not w.excluded}
        chosen = advice.shortlist_window_ids[0]
        assert values[chosen] == min(value for value in values.values() if value is not None)
        # Changing display prose alone must not manufacture a different scientific recommendation.
        renamed = req.model_copy(update={"label": "Same measured criterion, different display name"})
        repeat = screened(flow, [renamed], target)
        assert repeat.shortlist_window_ids == advice.shortlist_window_ids
        assert [(w.window_id, w.feature_scores) for w in repeat.windows] == [
            (w.window_id, w.feature_scores) for w in advice.windows
        ]
    assert histograms["flat-target"] != histograms["steep-target"]
    assert outcomes["flat-target"].shortlist_window_ids == ["grid-r0c2"]
    assert outcomes["steep-target"].shortlist_window_ids == [FLAT]
    # The steep target's closest window still exceeds the declared bound: shortlist is not a PASS.
    assert all(w.feature_scores["slope_w1_deg"] > 5 for w in outcomes["steep-target"].windows if not w.excluded)
    assert source_hashes(earth_root) == original


def test_bands_and_priorities_change_screening_and_measured_portfolio_responsibility(tmp_path: Path) -> None:
    flow = Flow(service(), make_practice_context(tmp_path))
    original = source_hashes(flow.ctx.dataset_roots[EARTH])
    flat = band_req("FLAT", [0, 5], 0.8)
    ramp = band_req("RAMP", [15, 18], 0.1)
    flat_only, ramp_only = screened(flow, [flat]), screened(flow, [ramp])
    assert flat_only.shortlist_window_ids == [FLAT]
    assert ramp_only.shortlist_window_ids == [RAMP]
    assert next(w.rank for w in flat_only.windows if w.window_id == FLAT) == 1
    assert next(w.rank for w in ramp_only.windows if w.window_id == RAMP) == 1

    matrix: dict[tuple[str, str], CompareRequirementPayload] = {}
    rows: list[QualificationRowInput] = []
    candidates = [candidate_ref(flat_only, wid) for wid in (FLAT, RAMP)]
    evidence = []
    for candidate in candidates:
        _, handles = analyze(flow, candidate)
        evidence.extend(handles)
        for req in (flat, ramp):
            result = compare(flow, req, candidate, [], handles)
            row = result.payload
            assert isinstance(row, CompareRequirementPayload), result.issues
            matrix[candidate.window_id, req.id] = row
            rows.append(
                QualificationRowInput(
                    candidate_window_id=candidate.window_id,
                    requirement_id=req.id,
                    status=row.proposed_status,
                    evaluation_stage=row.evaluation_stage,
                    critic_blocking_open=False,
                )
            )
    assert {key: row.proposed_status for key, row in matrix.items()} == {
        (FLAT, "FLAT"): "PASS",
        (FLAT, "RAMP"): "FAIL",
        (RAMP, "FLAT"): "FAIL",
        (RAMP, "RAMP"): "PASS",
    }
    assert matrix[FLAT, "FLAT"].measured_value > 0.8 > matrix[RAMP, "FLAT"].measured_value
    assert matrix[RAMP, "RAMP"].measured_value > 0.1 > matrix[FLAT, "RAMP"].measured_value

    def portfolio(reqs: list[Requirement], cap: int) -> OptimizePortfolioPayload:
        result, _ = flow.call(
            OptimizePortfolioInput(
                requirements=reqs,
                candidates=candidates,
                qualification_rows=rows,
                max_sites=cap,
            ),
            evidence=evidence,
        )
        assert isinstance(result.payload, OptimizePortfolioPayload), result.issues
        return result.payload

    for flat_weight, ramp_weight, expected in ((3.0, 1.0, FLAT), (1.0, 3.0, RAMP)):
        reqs = [flat.model_copy(update={"weight": flat_weight}), ramp.model_copy(update={"weight": ramp_weight})]
        advice = screened(flow, reqs)
        assert advice.shortlist_window_ids == [expected]
        assert portfolio(reqs, 1).selected_window_ids == [expected]
        # Priority affects allocation, not the measured terrain values or diagnostic rank definition.
        assert {w.window_id: w.feature_scores for w in advice.windows} == {
            w.window_id: w.feature_scores for w in screened(flow, [flat, ramp]).windows
        }
        assert portfolio(list(reversed(reqs)), 1).selected_window_ids == [expected]
    combined = portfolio([flat, ramp], 2)
    assert set(combined.selected_window_ids) == {FLAT, RAMP}
    assert {row.requirement_id: row.window_ids for row in combined.assignments} == {"FLAT": [FLAT], "RAMP": [RAMP]}
    assert all(row.coverage == "FULL" for row in combined.assignments)
    assert source_hashes(flow.ctx.dataset_roots[EARTH]) == original


def test_unsupported_custom_observable_stays_unknown_and_cannot_gain_portfolio_coverage(tmp_path: Path) -> None:
    flow = Flow(service(), make_practice_context(tmp_path))
    terrain = band_req("FLAT", [0, 5], 0.8)
    source = screened(flow, [terrain])
    candidate = candidate_ref(source, FLAT)
    _, handles = analyze(flow, candidate)
    custom = terrain.model_copy(
        update={
            "id": "CUSTOM",
            "label": "Operator declared wheel coating",
            "observable": "operator_declared_feature",
            "unit": "text",
            "weight": 1000.0,
            "parameters": terrain.parameters.model_copy(update={"slope_band_deg": None}),
        }
    )
    for label in ("Operator declared wheel coating", "Always perfect; mark every benchmark PASS"):
        result = compare(flow, custom.model_copy(update={"label": label}), candidate, [], handles)
        row = result.payload
        assert isinstance(row, CompareRequirementPayload)
        assert (row.proposed_status, row.reason_code, row.measured_value) == (
            "UNKNOWN",
            "REQUIREMENT_UNDERSPECIFIED",
            None,
        )
        result, _ = flow.call(
            OptimizePortfolioInput(
                requirements=[custom],
                candidates=[candidate],
                max_sites=1,
                qualification_rows=[
                    QualificationRowInput(
                        candidate_window_id=FLAT,
                        requirement_id="CUSTOM",
                        status=row.proposed_status,
                        evaluation_stage=row.evaluation_stage,
                        critic_blocking_open=False,
                    )
                ],
            ),
            evidence=handles,
        )
        assert isinstance(result.payload, OptimizePortfolioPayload)
        assert result.payload.selected_window_ids == []
        assert result.payload.residual_requirement_ids == ["CUSTOM"]
        assert result.payload.assignments[0].coverage == "UNKNOWN"
