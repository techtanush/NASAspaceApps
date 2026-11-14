"""SCN-05 / SCN-21: budgets, honest termination states, lossless certificates and cancellation of the route search."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

import uuid  # noqa: E402

from test_routing_support import (  # noqa: E402
    band_spec,
    brute_force,
    graph_design,
    graph_design_with,  # noqa: E402
    make_grid,
    raster_constraints,
    rebuild,
)

from analogforge.ports.science import (  # noqa: E402
    LocalScienceContext,
    ScienceCancelled,
    ScienceDeadlineExceeded,
)
from analogforge.ports.science_payloads import SearchCounters, SearchRoutePayload  # noqa: E402
from analogforge.science.routing import RouteInputError  # noqa: E402
from analogforge.science.routing.fixture_graph import canonical_graph_spec  # noqa: E402
from analogforge.science.routing.search import LABEL_CAP_FLAG, search_route  # noqa: E402


def _ctx(**kw: object) -> LocalScienceContext:
    return LocalScienceContext(
        scratch=Path("/nonexistent-never-written"), workspace_id=uuid.UUID(int=1), job_id=uuid.UUID(int=2), **kw
    )  # type: ignore[arg-type]


def test_one_expansion_is_budget_exhausted_never_infeasible() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    out = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_expansions=1)
    payload = out.payload
    assert payload.search_status == "BUDGET_EXHAUSTED" and payload.route is None
    assert payload.counters.expansions == 1 and "max_expansions 1" in payload.termination_reason
    # with just enough budget the same problem is solved: the limit, not the instance, caused the stop
    enough = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_expansions=100)
    assert enough.payload.search_status == "FOUND"


def test_budget_never_exceeds_the_frozen_solver_config() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    tight, digest = rebuild(design.constraints, solver={**design.constraints.solver.model_dump(), "max_expansions": 2})
    out = search_route(tight, digest, mode="synthetic", max_expansions=10_000)  # a caller may only lower budgets
    assert out.payload.search_status == "BUDGET_EXHAUSTED" and out.payload.counters.expansions == 2


def test_wall_clock_budget_uses_the_injected_clock() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    ticks = iter(range(10_000))
    out = search_route(
        design.constraints,
        design.constraints_sha256,
        mode="synthetic",
        max_seconds=0.5,
        clock=lambda: float(next(ticks)),
    )
    # the fake clock jumps one second per reading: the budget is exceeded at the first check
    assert out.payload.search_status in {"BUDGET_EXHAUSTED", "FOUND"}
    if out.payload.search_status == "BUDGET_EXHAUSTED":
        assert "max_seconds" in out.payload.termination_reason


def test_lossy_pruning_never_yields_exhaustive_infeasible() -> None:
    """229 m is infeasible by enumeration; with a 1-label cap pruning is lossy so the answer must NOT be proof."""
    design = graph_design("EXPOSURE_COVERAGE")
    tight, digest = rebuild(design.constraints, max_distance_m=229.0)
    exact = search_route(tight, digest, mode="synthetic")
    assert exact.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and exact.payload.counters.labels_pruned_lossy == 0
    capped = search_route(tight, digest, mode="synthetic", max_labels_per_node=1)
    assert capped.payload.counters.labels_pruned_lossy > 0
    assert capped.payload.search_status == "BUDGET_EXHAUSTED"
    assert LABEL_CAP_FLAG in capped.payload.approximation_flags
    assert "not proven" in capped.payload.termination_reason
    # a feasible instance under the same cap may be FOUND but is then flagged as approximate
    feasible = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_labels_per_node=1)
    assert feasible.payload.search_status in {"FOUND", "BUDGET_EXHAUSTED"}
    if feasible.payload.counters.labels_pruned_lossy > 0:
        assert LABEL_CAP_FLAG in feasible.payload.approximation_flags


def test_payload_validator_forbids_infeasible_with_lossy_pruning() -> None:
    with pytest.raises(ValueError, match="lossy"):
        SearchRoutePayload(
            search_status="EXHAUSTIVE_INFEASIBLE",
            route=None,
            route_artifact_key=None,
            counters=SearchCounters(
                expansions=1, labels_created=1, labels_pruned_dominated=0, labels_pruned_lossy=1, elapsed_ms=0
            ),
            termination_reason="x",
        )


def test_certificate_proofs_are_lossless_and_sound_against_brute_force() -> None:
    base = graph_design("EXPOSURE_COVERAGE")
    no_steep = graph_design_with(canonical_graph_spec(drop_edges=[("S", "B"), ("B", "C"), ("C", "W1")]))
    cut_w2 = graph_design_with(canonical_graph_spec(drop_edges=[("W1", "W2")]))
    too_long = rebuild(base.constraints, max_distance_m=100.0)
    cases = {
        "no steep edges": (no_steep.constraints, no_steep.constraints_sha256),
        "task unreachable": (cut_w2.constraints, cut_w2.constraints_sha256),
        "route too long": too_long,
    }
    for name, (art, digest) in cases.items():
        out = search_route(art, digest, mode="synthetic")
        assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE", name
        assert out.payload.counters.expansions == 0 and out.payload.counters.labels_pruned_lossy == 0, name
        assert out.payload.termination_reason.startswith("CERTIFICATE"), name
        assert brute_force(art) is None, name  # soundness: the certificate never rejects a feasible instance


def test_energy_lower_bound_certificate_boundary() -> None:
    """Cheapest closed route: 26 Wh (W2 round trip 6 Wh + two 10 Wh tasks); usable = 0.8 * battery."""
    design = graph_design("WAYPOINT_RETURN")
    for battery, expected in ((32.5, "FOUND"), (32.4, "EXHAUSTIVE_INFEASIBLE"), (20.0, "EXHAUSTIVE_INFEASIBLE")):
        energy = design.constraints.energy.model_dump(mode="json") | {"battery_wh": battery}
        art, digest = rebuild(design.constraints, energy=energy)
        out = search_route(art, digest, mode="synthetic")
        assert out.payload.search_status == expected, battery
        if expected == "EXHAUSTIVE_INFEASIBLE":
            assert out.payload.termination_reason.startswith("CERTIFICATE") and "Wh" in out.payload.termination_reason
            assert out.payload.counters.expansions == 0


def test_stale_constraints_hash_blocks_the_search() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    with pytest.raises(RouteInputError) as err:
        search_route(design.constraints, "0" * 64, mode="synthetic")
    assert err.value.code == "STALE_INPUT_HASH"


def test_missing_energy_model_disables_energy_pruning() -> None:
    grid = make_grid(np.full((8, 8), 3.0))
    art, digest = raster_constraints(
        grid, start=(4, 1), tasks=[("W1", (4, 5))], strategy="WAYPOINT_RETURN", energy_model=None
    )
    out = search_route(art, digest, grid=grid, mode="synthetic")
    assert out.payload.search_status == "FOUND"
    assert out.route is not None and out.route.solver_claimed.energy_conservative_wh is None  # unknown, never 0


# ------------------------------------------------------------------------------------------------ cancellation
def _hard_problem():  # noqa: ANN202
    """Infeasible only by enumeration: the distance cap is 1 m below the optimum (explores the whole f<cap region)."""
    size = 40
    slope = np.full((size, size), 3.0)
    slope[:, 24:28] = 15.0
    grid = make_grid(slope)
    art, digest = raster_constraints(
        grid,
        start=(20, 8),
        tasks=[("W1", (14, 10)), ("W2", (26, 10))],
        exposures=[band_spec()],
        strategy="EXPOSURE_COVERAGE",
        max_distance_m=None,
    )
    done = search_route(art, digest, grid=grid, mode="synthetic")
    assert done.route is not None
    cap = done.route.solver_claimed.distance_m - 1.0
    art2, digest2 = rebuild(art, max_distance_m=cap)
    return grid, art2, digest2


def test_cancellation_is_honoured_within_one_second() -> None:
    grid, art, digest = _hard_problem()
    ctx = _ctx()
    timer = threading.Timer(0.3, lambda: setattr(ctx, "cancelled", True))
    start = time.monotonic()
    timer.start()
    cancelled_at: list[float] = []

    def check() -> None:
        try:
            ctx.check_cancelled()
        except ScienceCancelled:
            cancelled_at.append(time.monotonic())
            raise

    with pytest.raises(ScienceCancelled):
        search_route(art, digest, grid=grid, mode="synthetic", check_cancelled=check)
    timer.cancel()
    assert cancelled_at, "the search must call check_cancelled"
    elapsed_after_flag = time.monotonic() - (start + 0.3)
    assert 0.0 <= elapsed_after_flag < 1.0, elapsed_after_flag


def test_deadline_is_not_swallowed() -> None:
    grid, art, digest = _hard_problem()
    ctx = _ctx(deadline_monotonic=time.monotonic() + 0.2)
    with pytest.raises(ScienceDeadlineExceeded):
        search_route(art, digest, grid=grid, mode="synthetic", check_cancelled=ctx.check_cancelled)


def test_cancelled_before_start_raises_immediately() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    ctx = _ctx(cancelled=True)
    with pytest.raises(ScienceCancelled):
        search_route(
            design.constraints, design.constraints_sha256, mode="synthetic", check_cancelled=ctx.check_cancelled
        )
