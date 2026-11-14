"""SCN-03: canonical graph - every ``catalog.GRAPH_EXPECTED`` entry through the REAL search and the REAL verifier,
brute-force oracle equality, lexicographic tie-break and mock-provider rejection in live mode."""

from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import (  # noqa: E402
    brute_force,
    brute_force_full,
    design_input,
    graph_design,
    graph_design_with,
    load_json,
    make_route,
    rebuild,
    rover,
)

from analogforge.ports import catalog  # noqa: E402
from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.ports.science_payloads import ConstraintsArtifact, GraphEdge, GraphSpec, Waypoint  # noqa: E402
from analogforge.science.routing import RouteInputError  # noqa: E402
from analogforge.science.routing.fixture_graph import CANONICAL_GRAPH_EDGES, canonical_graph_spec  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402
from analogforge.science.routing.waypoints import design_benchmark  # noqa: E402

EXPECTED = catalog.GRAPH_EXPECTED


def _metric(out, metric_id):  # noqa: ANN001, ANN202
    return next(m.value for m in out.payload.metrics if m.metric_id == metric_id)


def _verify_supplied(sequence, strategy="EXPOSURE_COVERAGE"):  # noqa: ANN001, ANN202
    design = graph_design(strategy)
    route = make_route(design.constraints_sha256, sequence, strategy=strategy)
    return design, verify_route(
        design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
    )


def _search_and_verify(strategy):  # noqa: ANN001, ANN202
    design = graph_design(strategy)
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    assert found.route is not None and found.route_sha256 is not None
    verified = verify_route(
        design.constraints, design.constraints_sha256, found.route, found.route_sha256, "FOUND", mode="synthetic"
    )
    return design, found, verified


def test_kit_expected_file_mirrors_catalog() -> None:
    fixture = load_json("expected/graph-expected.json")
    for key, entry in EXPECTED.items():
        for field, value in entry.items():
            assert fixture[key][field] == value


def test_in_code_canonical_graph_equals_kit_fixture() -> None:
    fixture = load_json("canonical-graph-v1.json")
    spec = canonical_graph_spec()
    assert spec.nodes == fixture["nodes"]
    assert [(e.a, e.b, e.length_m, e.surface_slope_deg, e.mock_energy_wh) for e in spec.edges] == [
        (e["a"], e["b"], e["length_m"], e["surface_slope_deg"], e["mock_energy_wh"]) for e in fixture["edges"]
    ]
    assert len(CANONICAL_GRAPH_EDGES) == len(fixture["edges"])


def test_supplied_fail_route_through_verifier() -> None:
    exp = EXPECTED["supplied_fail"]
    _, out = _verify_supplied(catalog.GRAPH_SUPPLIED_ROUTE_FAIL)
    assert out.payload.outcome == exp["outcome"]
    assert out.payload.failure_category == exp["category"]
    assert [v.code for v in out.payload.violations] == [exp["violation"]]
    assert _metric(out, "route_distance_m") == exp["distance_m"]
    assert _metric(out, "energy_conservative_wh") == exp["energy_wh"]
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == exp["unique_exposure_m"]
    assert out.payload.verified_route_sha256 is None
    violation = out.payload.violations[0]
    assert violation.constraint_id == catalog.constraint_exposure("R-EXPOSURE")
    assert (violation.observed, violation.threshold, violation.unit) == (0.0, 100.0, "m")


def test_supplied_pass_route_through_verifier() -> None:
    exp = EXPECTED["supplied_pass"]
    _, out = _verify_supplied(catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    assert out.payload.outcome == exp["outcome"]
    assert out.payload.failure_category is None and out.payload.violations == []
    assert _metric(out, "route_distance_m") == exp["distance_m"]
    assert _metric(out, "energy_conservative_wh") == exp["energy_wh"]
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == exp["unique_exposure_m"]
    assert _metric(out, "reserve_pct") == pytest.approx(exp["reserve_pct"], abs=1e-12)
    assert out.payload.verified_route_sha256 == out.route_sha256


def test_search_waypoint_return_matches_expected_and_verifies_fail() -> None:
    exp = EXPECTED["search_waypoint_return"]
    _, found, out = _search_and_verify("WAYPOINT_RETURN")
    assert found.payload.search_status == exp["search_status"]
    assert tuple(found.route.node_sequence) == catalog.GRAPH_SEARCH_WAYPOINT_RETURN  # type: ignore[union-attr]
    assert out.payload.outcome == exp["outcome"] and out.payload.failure_category == exp["category"]
    assert _metric(out, "route_distance_m") == exp["distance_m"]
    assert _metric(out, "energy_conservative_wh") == exp["energy_wh"]
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == exp["unique_exposure_m"]
    assert found.payload.counters.labels_pruned_lossy == 0 and found.payload.approximation_flags == []


def test_search_exposure_coverage_matches_expected_and_verifies_pass() -> None:
    exp = EXPECTED["search_exposure_coverage"]
    _, found, out = _search_and_verify("EXPOSURE_COVERAGE")
    assert found.payload.search_status == exp["search_status"]
    assert tuple(found.route.node_sequence) == catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE  # type: ignore[union-attr]
    assert out.payload.outcome == exp["outcome"]
    assert _metric(out, "route_distance_m") == exp["distance_m"]
    assert _metric(out, "energy_conservative_wh") == exp["energy_wh"]
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == exp["unique_exposure_m"]
    assert _metric(out, "reserve_pct") == pytest.approx(exp["reserve_pct"], abs=1e-12)


def test_one_expansion_budget_is_budget_exhausted_with_search_limit_diagnosis() -> None:
    from analogforge.ports.science_payloads import DiagnoseResultInput, VerificationSummary
    from analogforge.science.routing.diagnose import diagnose_result

    exp = EXPECTED["one_expansion_budget"]
    design = graph_design("EXPOSURE_COVERAGE")
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_expansions=1)
    assert found.payload.search_status == exp["search_status"]
    assert found.route is None and found.payload.counters.expansions == 1
    diag = diagnose_result(
        DiagnoseResultInput(
            constraints=design.constraints,
            search_status="BUDGET_EXHAUSTED",
            verification=VerificationSummary(outcome=exp["outcome"], failure_category=exp["category"]),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        ),
        mode="synthetic",
    ).payload
    assert diag.primary_category == exp["category"]
    assert diag.proof_scope == "bounded search; not proof that no route exists"
    assert diag.recommended_strategy in {"MINIMUM_FEASIBLE_ROUTE", "WAYPOINT_RETURN"}  # a *different*, untried strategy


def test_steep_edges_removed_is_lossless_exhaustive_infeasible() -> None:
    exp = EXPECTED["steep_edges_removed"]
    spec = canonical_graph_spec(drop_edges=[("S", "B"), ("B", "C"), ("C", "W1")])
    design = graph_design_with(spec, "EXPOSURE_COVERAGE")
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    assert found.payload.search_status == exp["search_status"]
    assert found.route is None
    assert found.payload.counters.labels_pruned_lossy == 0
    assert found.payload.optimistic_exposure_bound_m == {"R-EXPOSURE": 0.0}
    # perturbation: with only the S-B edge dropped, B-C-W1 is still reachable via A-W1 -> feasible again
    partial = graph_design_with(canonical_graph_spec(drop_edges=[("S", "B")]), "EXPOSURE_COVERAGE")
    again = search_route(partial.constraints, partial.constraints_sha256, mode="synthetic")
    assert again.payload.search_status == "FOUND"
    assert again.route is not None and "B" in again.route.node_sequence


def test_exhaustive_by_enumeration_when_certificate_cannot_prove() -> None:
    """max_distance 229 < 230 m: optimistic bounds pass (exposure bound 150, tasks 120 m) but no route exists."""
    design = graph_design("EXPOSURE_COVERAGE")
    tight, digest = rebuild(design.constraints, max_distance_m=229.0)
    found = search_route(tight, digest, mode="synthetic")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert found.payload.counters.labels_pruned_lossy == 0
    assert found.payload.counters.expansions > 0  # decided by enumeration, not by the certificate
    assert brute_force(tight) is None
    exact, exact_digest = rebuild(design.constraints, max_distance_m=230.0)
    ok = search_route(exact, exact_digest, mode="synthetic")
    assert ok.payload.search_status == "FOUND" and ok.payload.route is not None


@pytest.mark.parametrize("strategy", ["WAYPOINT_RETURN", "EXPOSURE_COVERAGE", "MINIMUM_FEASIBLE_ROUTE"])
def test_search_equals_brute_force_oracle(strategy: str) -> None:
    design = graph_design(strategy)  # type: ignore[arg-type]
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    oracle = brute_force(design.constraints)
    assert oracle is not None and found.route is not None
    distance, energy, sequence, _ = oracle
    assert tuple(found.route.node_sequence) == sequence
    assert found.route.solver_claimed.distance_m == pytest.approx(distance)
    assert found.route.solver_claimed.energy_conservative_wh == pytest.approx(energy)


def test_lexicographic_tie_break_is_observable() -> None:
    """Two distinct 230 m / 30 Wh routes exist; the search returns the lexicographically smaller one."""
    design = graph_design("EXPOSURE_COVERAGE")
    twin_a = ("S", "A", "W1", "W2", "W1", "C", "B", "S")
    twin_b = ("S", "B", "C", "W1", "W2", "W1", "A", "S")
    verdicts = []
    for twin in (twin_a, twin_b):
        route = make_route(design.constraints_sha256, twin)
        out = verify_route(
            design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
        )
        verdicts.append((_metric(out, "route_distance_m"), _metric(out, "energy_conservative_wh"), out.payload.outcome))
    assert verdicts[0] == verdicts[1] == (230.0, 30.0, "PASS")  # genuine tie
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    assert found.route is not None
    assert tuple(found.route.node_sequence) == twin_a
    assert twin_a < twin_b


def test_energy_breaks_distance_ties_before_lexicographic_order() -> None:
    """Same distance, different energy: the cheaper route wins even if it is lexicographically larger."""
    edges = [
        GraphEdge(a="S", b="A", length_m=20, surface_slope_deg=10, mock_energy_wh=5),
        GraphEdge(a="A", b="W1", length_m=20, surface_slope_deg=10, mock_energy_wh=5),
        GraphEdge(a="S", b="B", length_m=20, surface_slope_deg=10, mock_energy_wh=1),
        GraphEdge(a="B", b="W1", length_m=20, surface_slope_deg=10, mock_energy_wh=1),
    ]
    spec = GraphSpec(nodes=["S", "A", "B", "W1"], edges=edges)
    design = graph_design_with(spec, "WAYPOINT_RETURN")
    only_w1, digest = rebuild(
        design.constraints, tasks=[t.model_dump(mode="json") for t in design.constraints.tasks[:1]]
    )
    found = search_route(only_w1, digest, mode="synthetic")
    assert found.route is not None
    assert found.route.node_sequence == [
        "S",
        "B",
        "W1",
        "B",
        "S",
    ]  # 4 Wh path beats the lexicographically smaller 20 Wh path
    oracle = brute_force(only_w1)
    assert oracle is not None and oracle[2] == tuple(found.route.node_sequence)


def test_pert09_longer_edge_changes_the_result() -> None:
    edges = [
        GraphEdge(
            a=a, b=b, length_m=500.0 if (a, b) == ("S", "B") else length, surface_slope_deg=slope, mock_energy_wh=wh
        )
        for a, b, length, slope, wh in CANONICAL_GRAPH_EDGES
    ]
    spec = GraphSpec(nodes=["S", "A", "B", "C", "W1", "W2"], edges=edges)
    design = graph_design_with(spec, "EXPOSURE_COVERAGE")
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    assert found.route is not None
    assert tuple(found.route.node_sequence) != catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE
    assert "S--B" not in {
        f"{min(a, b)}--{max(a, b)}"
        for a, b in zip(found.route.node_sequence, found.route.node_sequence[1:], strict=False)
    }
    assert found.route.solver_claimed.distance_m <= 400.0
    oracle = brute_force(design.constraints)
    assert oracle is not None and oracle[2] == tuple(found.route.node_sequence)


def test_requirement_threshold_perturbation_flips_feasibility() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    base = design.constraints.model_dump(mode="json")
    for minimum, status in ((150.0, "FOUND"), (151.0, "EXHAUSTIVE_INFEASIBLE")):
        data = {**base, "exposures": [{**base["exposures"][0], "minimum_distance_m": minimum}]}
        changed = ConstraintsArtifact.model_validate(data)
        out = search_route(changed, canonical_sha256(changed), mode="synthetic")
        assert out.payload.search_status == status, minimum


def test_mock_provider_rejected_in_live_mode() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    # (1) the kit model itself refuses a live mock artifact
    with pytest.raises(ValueError, match="TEST_ONLY_MOCK_GRAPH"):
        ConstraintsArtifact.model_validate({**design.constraints.model_dump(mode="json"), "mode": "live"})
    # (2) designing the graph scenario outside synthetic mode is refused
    for mode in ("live", "replay"):
        with pytest.raises(RouteInputError) as err:
            design_benchmark(design_input("EXPOSURE_COVERAGE"), mode=mode)  # type: ignore[arg-type]
        assert err.value.detail_code == "MOCK_PROVIDER_FORBIDDEN"
    # (3) search and verify refuse a synthetic mock artifact when the request runs live
    with pytest.raises(RouteInputError) as err:
        search_route(design.constraints, design.constraints_sha256, mode="live")
    assert err.value.detail_code == "MOCK_PROVIDER_FORBIDDEN"
    route = make_route(design.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    with pytest.raises(RouteInputError):
        verify_route(
            design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="live"
        )


def test_mock_energy_ignores_rover_energy_model_and_margin() -> None:
    """The mock provider is accounting-only: a 25 % uncertainty margin in the rover model must not leak in."""
    design = graph_design("EXPOSURE_COVERAGE", rover_obj=rover("ares-1"))
    assert design.constraints.energy.model is not None and design.constraints.energy.model.uncertainty_fraction == 0.25
    _, out = _verify_supplied(catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    assert _metric(out, "energy_nominal_wh") == _metric(out, "energy_conservative_wh") == 34.0


def test_band_boundaries_are_lower_inclusive_upper_exclusive_except_the_final_band() -> None:
    from analogforge.science.routing.exposure import slope_in_band

    assert slope_in_band(12.0, (12.0, 18.0), False) and not slope_in_band(11.999, (12.0, 18.0), False)
    assert not slope_in_band(18.0, (12.0, 18.0), False) and slope_in_band(18.0, (12.0, 18.0), True)
    # a 12 deg sample belongs to the 12-15 band only, not to 9-12
    assert slope_in_band(12.0, (12.0, 15.0), False) and not slope_in_band(12.0, (9.0, 12.0), False)
    # through the verifier: the 15 deg edges re-labelled 18 deg count only for a final (inclusive) band
    steep = GraphSpec(
        nodes=["S", "A", "B", "C", "W1", "W2"],
        edges=[
            GraphEdge(a=a, b=b, length_m=length, surface_slope_deg=18.0 if slope == 15.0 else slope, mock_energy_wh=wh)
            for a, b, length, slope, wh in CANONICAL_GRAPH_EDGES
        ],
    )
    design = graph_design_with(steep, "EXPOSURE_COVERAGE")
    assert design.constraints.exposures[0].upper_inclusive is True
    inclusive = design.constraints
    exclusive_data = inclusive.exposures[0].model_dump(mode="json") | {"upper_inclusive": False}
    exclusive, digest = rebuild(inclusive, exposures=[exclusive_data])
    for art, dig, expected in ((inclusive, design.constraints_sha256, 150.0), (exclusive, digest, 0.0)):
        route = make_route(dig, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
        out = verify_route(art, dig, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
        assert _metric(out, "unique_exposure_m:R-EXPOSURE") == expected


def test_traversal_limit_binds_the_search() -> None:
    """W2 is a dead end: with at most ONE traversal per edge no closed route exists; with two it does (and a loop
    variant of the graph is feasible with one)."""
    design = graph_design("WAYPOINT_RETURN")
    one, digest_one = rebuild(design.constraints, max_undirected_edge_traversals=1)
    out = search_route(one, digest_one, mode="synthetic")
    assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and brute_force(one) is None
    assert out.payload.counters.expansions > 0  # decided by enumeration, not by the certificate
    two, digest_two = rebuild(design.constraints, max_undirected_edge_traversals=2)
    assert search_route(two, digest_two, mode="synthetic").payload.search_status == "FOUND"
    # verifier agrees: the dead-end out-and-back needs two traversals
    route = make_route(digest_one, catalog.GRAPH_SEARCH_WAYPOINT_RETURN, strategy="WAYPOINT_RETURN")
    ver = verify_route(one, digest_one, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
    assert "EDGE_TRAVERSAL_LIMIT_EXCEEDED" in {v.code for v in ver.payload.violations}


# ----------------------------------------------------------------------------------------------- random-graph oracle
def _random_case(seed: int) -> tuple[ConstraintsArtifact, str]:
    """Deterministic random abstract scenario: 3-5 nodes, random edges, any strategy, traversal limit 1 or 2, UNIQUE or
    TOTAL exposure counting, optional distance cap and a tight/loose battery."""
    rng = random.Random(seed)  # noqa: S311
    nodes = [f"N{i}" for i in range(rng.randint(3, 5))]
    pairs = [(a, b) for a, b in itertools.combinations(nodes, 2) if rng.random() < 0.6] or [(nodes[0], nodes[1])]
    spec = GraphSpec(
        nodes=nodes,
        edges=[
            GraphEdge(
                a=a,
                b=b,
                length_m=float(rng.choice([10, 20, 30, 40, 50])),
                surface_slope_deg=float(rng.choice([5, 10, 12, 15, 18])),
                mock_energy_wh=float(rng.choice([0.5, 1, 2, 3])),
            )
            for a, b in pairs
        ],
    )
    strategy = rng.choice(["EXPOSURE_COVERAGE", "WAYPOINT_RETURN", "MINIMUM_FEASIBLE_ROUTE"])
    base = graph_design_with(spec, strategy).constraints  # type: ignore[arg-type]
    n_tasks = rng.randint(1, 2)
    task_nodes = rng.sample(nodes, n_tasks)
    tasks = [
        t.model_copy(update={"task_id": f"T{i}", "location": Waypoint(node_id=n)})
        for i, (t, n) in enumerate(zip(base.tasks, task_nodes, strict=False))
    ][:n_tasks]
    exposures = [
        e.model_copy(
            update={
                "minimum_distance_m": float(rng.choice([0, 20, 40, 60, 100, 150])),
                "counting": rng.choice(["UNIQUE_UNDIRECTED_EDGE_DISTANCE", "TOTAL_TRAVERSED_DISTANCE"]),
            }
        )
        for e in base.exposures
    ]
    max_traversals = rng.choice([1, 2])
    max_distance = rng.choice([None, 100.0, 200.0, 300.0])
    energy = base.energy.model_copy(update={"battery_wh": float(rng.choice([20, 50, 1000]))})
    art = base.model_copy(
        update={
            "start": Waypoint(node_id=rng.choice(nodes)),
            "tasks": tasks,
            "exposures": exposures,
            "max_undirected_edge_traversals": max_traversals,
            "max_distance_m": max_distance,
            "energy": energy,
        }
    )
    art = ConstraintsArtifact.model_validate(art.model_dump(mode="json"))
    return art, canonical_sha256(art)


def _check_against_oracle(seed: int) -> None:
    constraints, digest = _random_case(seed)
    out = search_route(constraints, digest, mode="synthetic")
    oracle = brute_force_full(constraints)
    status = out.payload.search_status
    context = f"seed {seed} {constraints.strategy} mt={constraints.max_undirected_edge_traversals}"
    if oracle is None:
        assert status == "EXHAUSTIVE_INFEASIBLE", f"{context}: oracle infeasible, search says {status}"
        return
    assert status == "FOUND", (
        f"{context}: oracle feasible {oracle}, search says {status}: {out.payload.termination_reason}"
    )
    assert out.route is not None and out.route_sha256 is not None
    assert tuple(out.route.node_sequence) == oracle[2], f"{context}: not the oracle optimum {oracle}"
    assert out.route.solver_claimed.distance_m == pytest.approx(oracle[0])
    if constraints.strategy != "WAYPOINT_RETURN":  # WAYPOINT_RETURN deliberately ignores exposure requirements
        ver = verify_route(constraints, digest, out.route, out.route_sha256, "FOUND", mode="synthetic")
        assert ver.payload.outcome == "PASS", f"{context}: {[v.code for v in ver.payload.violations]}"


# seeds that exposed the traversal-limit-1 dominance defect (reviewer finding) plus a TOTAL-counting one
@pytest.mark.parametrize("seed", [1047, 1071, 1074, 1115])
def test_traversal_limit_one_dominance_regressions(seed: int) -> None:
    constraints, _ = _random_case(seed)
    assert constraints.max_undirected_edge_traversals == 1
    _check_against_oracle(seed)


def test_search_equals_exhaustive_oracle_over_random_graphs_all_strategies_limits_and_counting() -> None:
    seen: set[tuple[str, int, str]] = set()
    for seed in range(260):
        _check_against_oracle(seed)
        art, _ = _random_case(seed)
        seen.add((art.strategy, art.max_undirected_edge_traversals, art.exposures[0].counting))
    assert len(seen) >= 12  # every strategy x {1,2} x {unique,total} combination was actually exercised


def test_total_counting_minimum_feasible_route_is_energy_minimal() -> None:
    """Dominance must not discard a prefix whose extra traversals count toward TOTAL exposure (seed 2143 family)."""
    edges = [
        ("N0", "N1", 40.0, 0.5, 10.0),
        ("N0", "N3", 30.0, 0.5, 15.0),
        ("N1", "N4", 20.0, 2.0, 15.0),
        ("N2", "N3", 20.0, 2.0, 10.0),
        ("N2", "N4", 10.0, 1.0, 15.0),
        ("N3", "N4", 50.0, 3.0, 10.0),
    ]
    spec = GraphSpec(
        nodes=[f"N{i}" for i in range(5)],
        edges=[
            GraphEdge(a=a, b=b, length_m=length, surface_slope_deg=slope, mock_energy_wh=wh)
            for a, b, length, wh, slope in edges
        ],
    )
    base = graph_design_with(spec, "MINIMUM_FEASIBLE_ROUTE").constraints
    task = base.tasks[0].model_copy(update={"task_id": "T0", "location": Waypoint(node_id="N3")})
    expo = base.exposures[0].model_copy(update={"minimum_distance_m": 100.0, "counting": "TOTAL_TRAVERSED_DISTANCE"})
    art = ConstraintsArtifact.model_validate(
        base.model_copy(
            update={
                "start": Waypoint(node_id="N2"),
                "tasks": [task],
                "exposures": [expo],
                "max_distance_m": None,
                "energy": base.energy.model_copy(update={"battery_wh": 50.0}),
            }
        ).model_dump(mode="json")
    )
    digest = canonical_sha256(art)
    out = search_route(art, digest, mode="synthetic")
    oracle = brute_force_full(art)
    assert oracle is not None and out.route is not None
    assert tuple(out.route.node_sequence) == oracle[2]
    assert (oracle[0], oracle[1]) == (200.0, 18.0)
    assert out.route.solver_claimed.energy_conservative_wh == pytest.approx(18.0)
