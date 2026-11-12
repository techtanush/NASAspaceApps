"""Cross-cutting science properties (hypothesis), exercised through the real functions with no mocks:

non-negative distance and energy, no invalid-cell traversal, monotone reserve with added work, no duplicate exposure
credit, and deterministic hashes.  The route-engine specific properties live in ``test_routing_properties.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

_SUPPORT = Path(__file__).resolve().parents[2] / "unit/science/test_routing_support.py"
_spec = importlib.util.spec_from_file_location("routing_test_support_p", _SUPPORT)
assert _spec is not None and _spec.loader is not None
support = importlib.util.module_from_spec(_spec)
sys.modules["routing_test_support_p"] = support
_spec.loader.exec_module(support)

from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.science.energy import EnergyAccumulator, EnergyParams, route_energy  # noqa: E402
from analogforge.science.geometry import body_distance_m  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402

FAST = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)

PARAMS = EnergyParams(
    mass_kg=42.0,
    nominal_speed_mps=0.5,
    battery_wh=1800.0,
    min_reserve_pct=20.0,
    rolling_coefficient=0.06,
    drive_efficiency=0.65,
    idle_power_w=35.0,
    science_task_wh=10.0,
    roughness_multiplier=1.0,
    uncertainty_fraction=0.25,
)
LON = st.floats(-179.0, 179.0)
LAT = st.floats(-85.0, 85.0)
EDGE = st.tuples(st.floats(0.0, 500.0), st.floats(-50.0, 50.0))


@FAST
@given(body=st.sampled_from(["EARTH", "MOON", "MARS"]), a=st.tuples(LON, LAT), b=st.tuples(LON, LAT))
def test_distance_is_non_negative_and_symmetric(body, a, b) -> None:  # noqa: ANN001
    d_ab = body_distance_m(body, a[0], a[1], b[0], b[1])
    d_ba = body_distance_m(body, b[0], b[1], a[0], a[1])
    assert d_ab >= 0.0 and abs(d_ab - d_ba) <= 1e-6 * max(1.0, d_ab)
    assert body_distance_m(body, a[0], a[1], a[0], a[1]) < 1e-6


@FAST
@given(edges=st.lists(EDGE, max_size=12), tasks=st.integers(0, 5), dwell=st.floats(0.0, 3600.0))
def test_energy_terms_are_non_negative(edges, tasks, dwell) -> None:  # noqa: ANN001
    e = route_energy(PARAMS, edges, tasks_completed=tasks, dwell_s_total=dwell)
    for value in (e.distance_xy_m, e.distance_surface_m, e.rolling_wh, e.climb_wh, e.idle_wh, e.tasks_wh,
                  e.nominal_wh, e.conservative_wh):  # fmt: skip
        assert value >= 0.0
    assert e.conservative_wh >= e.nominal_wh and e.distance_surface_m >= e.distance_xy_m


@FAST
@given(first=st.lists(EDGE, max_size=8), extra=st.lists(EDGE, min_size=1, max_size=6))
def test_reserve_never_increases_when_work_is_added(first, extra) -> None:  # noqa: ANN001
    acc = EnergyAccumulator(PARAMS)
    for d, z in first:
        acc.add_edge(d, z)
    before = acc.total()
    for d, z in extra:
        acc.add_edge(d, z)
        assert acc.total().reserve_pct <= before.reserve_pct
    assert acc.total().conservative_wh >= before.conservative_wh


@FAST
@given(size=st.integers(6, 9), seed=st.integers(0, 2**31 - 1), blocked=st.sampled_from([0.0, 0.1, 0.25]))
def test_routes_never_traverse_invalid_cells(size: int, seed: int, blocked: float) -> None:
    rng = np.random.default_rng(seed)
    valid = rng.random((size, size)) > blocked
    land = np.ones((size, size), dtype=bool)
    slope = rng.choice([2.0, 6.0, 21.0], size=(size, size))
    good = valid & (np.where(valid, slope, np.inf) <= 18.0)
    cells = [(r, c) for r in range(size) for c in range(size) if good[r, c]]
    if len(cells) < 3:
        return
    grid = support.make_grid(slope, valid=valid, land=land)
    art, digest = support.raster_constraints(
        grid, start=cells[0], tasks=[("W1", cells[-1])], strategy="WAYPOINT_RETURN", energy_model=None,
        max_distance_m=None, task_tolerance_m=0.0,
    )  # fmt: skip
    out = search_route(art, digest, grid=grid, mode="synthetic")
    if out.route is None:
        return
    for node in out.route.node_sequence:
        r, c = int(node[1 : node.index("c")]), int(node[node.index("c") + 1 :])
        assert good[r, c]


@FAST
@given(repeats=st.integers(0, 6))
def test_repeating_an_exposed_edge_never_adds_unique_exposure(repeats: int) -> None:
    design = support.graph_design("EXPOSURE_COVERAGE")
    base = ["S", "B", "S"]
    metrics = []
    for k in (0, repeats):
        walk = [*base[:-1], *(["B", "S"] * k), "S"] if k else base
        route = support.make_route(design.constraints_sha256, walk)
        out = verify_route(
            design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
        )
        metrics.append({m.metric_id: m.value for m in out.payload.metrics})
    assert metrics[0]["unique_exposure_m:R-EXPOSURE"] == metrics[1]["unique_exposure_m:R-EXPOSURE"]
    assert metrics[1]["traversed_exposure_m:R-EXPOSURE"] >= metrics[0]["traversed_exposure_m:R-EXPOSURE"]


JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers(-(10**9), 10**9) | st.text(max_size=8),
    lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=5), c, max_size=3),
    max_leaves=12,
)


@FAST
@given(doc=st.dictionaries(st.text(min_size=1, max_size=6), JSON_VALUES, min_size=1, max_size=6), data=st.data())
def test_canonical_hash_is_deterministic_and_key_order_independent(doc, data) -> None:  # noqa: ANN001
    keys = data.draw(st.permutations(list(doc)))
    reordered = {k: doc[k] for k in keys}
    digest = canonical_sha256(doc)
    assert digest == canonical_sha256(reordered) == canonical_sha256(dict(doc))
    assert len(digest) == 64 and digest == digest.lower()
