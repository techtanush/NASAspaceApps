"""R-CFG-01: routing reads its tunables from ``config/algorithms.yaml`` (copied here with changed values)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))

from test_graph_oracle import EXPECTED  # noqa: E402
from test_routing_support import (  # noqa: E402
    band_spec,
    design_input,
    grid_spec_of,
    make_grid,
    mission,
    ramp_grid,
    raster_constraints,
    rover,
)

from analogforge.ports import catalog  # noqa: E402
from analogforge.science.config import default_config_dir, load_config  # noqa: E402
from analogforge.science.routing.constraints import RouteDesignDefaults, route_defaults_from_config  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402
from analogforge.science.routing.waypoints import design_benchmark  # noqa: E402


def _config_with(tmp_path: Path, edit) -> object:  # noqa: ANN001
    for name in ("algorithms.yaml", "candidates.yaml", "datasets.yaml"):
        shutil.copy(default_config_dir() / name, tmp_path / name)
    raw = yaml.safe_load((tmp_path / "algorithms.yaml").read_text())
    edit(raw)
    (tmp_path / "algorithms.yaml").write_text(yaml.safe_dump(raw))
    return load_config(tmp_path)


def _design(grid, defaults):  # noqa: ANN001, ANN202
    inp = design_input(
        "WAYPOINT_RETURN",
        rover_obj=rover("ares-1"),
        mission_obj=mission("mission-mars-mobility"),
        graph=False,
        window_id=catalog.WINDOW_B_CORRIDOR,
    )
    return design_benchmark(inp, mode="synthetic", grid=grid, grid_spec=grid_spec_of(grid), defaults=defaults)


def _ramp_window() -> object:
    slope = np.full((64, 64), 3.0)
    slope[8:56, 40:50] = 15.0
    return make_grid(slope)


def test_production_config_reproduces_the_literal_defaults() -> None:
    cfg = load_config()
    assert route_defaults_from_config(cfg.algorithms) == RouteDesignDefaults()
    # and design_benchmark(defaults=None) uses that config, so the oracle values are unchanged
    assert EXPECTED["search_exposure_coverage"]["distance_m"] == 230.0


def test_max_edge_traversals_flows_into_graph_and_raster_constraints(tmp_path: Path) -> None:
    cfg = _config_with(tmp_path, lambda raw: raw["route_search"].__setitem__("max_edge_traversals", 3))
    defaults = route_defaults_from_config(cfg.algorithms)  # type: ignore[attr-defined]
    assert defaults.max_edge_traversals == 3
    graph = design_benchmark(design_input("EXPOSURE_COVERAGE"), mode="synthetic", defaults=defaults)
    assert graph.constraints.max_undirected_edge_traversals == 3
    assert (
        graph.constraints_sha256
        != design_benchmark(design_input("EXPOSURE_COVERAGE"), mode="synthetic").constraints_sha256
    )
    raster = _design(_ramp_window(), defaults)
    assert raster.constraints.max_undirected_edge_traversals == 3
    assert _design(_ramp_window(), None).constraints.max_undirected_edge_traversals == 2


def test_auto_waypoint_rule_comes_from_config(tmp_path: Path) -> None:
    grid = _ramp_window()
    base = _design(grid, None).constraints
    cfg = _config_with(
        tmp_path,
        lambda raw: raw["design_defaults"]["auto_waypoints"].update(
            w1_min_edge_fraction=0.20, w1_max_edge_fraction=0.40, tolerance_cells=2
        ),
    )
    changed = _design(grid, route_defaults_from_config(cfg.algorithms)).constraints  # type: ignore[attr-defined]
    assert [t.location for t in changed.tasks] != [t.location for t in base.tasks]
    assert all(t.tolerance_m == 2 * grid.cell_size_m for t in changed.tasks)
    assert all(t.tolerance_m == grid.cell_size_m for t in base.tasks)
    # the W1 distance from the start obeys the configured annulus (0.20-0.40 of the 64-cell edge)
    from analogforge.science.routing import parse_raster_node_id

    sr, sc = parse_raster_node_id(changed.start.node_id)  # type: ignore[arg-type]
    wr, wc = parse_raster_node_id(changed.tasks[0].location.node_id)  # type: ignore[arg-type]
    d_cells = float(np.hypot(sr - wr, sc - wc))
    assert 0.20 * 64 - 1e-6 <= d_cells <= 0.40 * 64 + 1e-6


def test_band_neighbourhood_comes_from_config(tmp_path: Path) -> None:
    grid = _ramp_window()
    cfg = _config_with(
        tmp_path, lambda raw: raw["design_defaults"]["auto_waypoints"].update(band_neighbourhood_cells=1)
    )
    one = _design(grid, route_defaults_from_config(cfg.algorithms)).constraints  # type: ignore[attr-defined]
    base = _design(grid, None).constraints
    assert [t.location for t in one.tasks] != [t.location for t in base.tasks]


def test_hazard_min_intersection_changes_exposure_and_the_outcome(tmp_path: Path) -> None:
    grid = ramp_grid(10, 24)
    expo = band_spec(12, 18, minimum=100.0)
    art, digest = raster_constraints(grid, start=(5, 13), tasks=[("W1", (5, 13))], exposures=[expo], max_distance_m=1e5)
    default = search_route(art, digest, grid=grid, mode="synthetic")
    assert default.payload.search_status == "FOUND"
    cfg = _config_with(tmp_path, lambda raw: raw["thresholds"].__setitem__("hazard_min_intersection_m", 45.0))
    hazard = cfg.algorithms.thresholds.hazard_min_intersection_m  # type: ignore[attr-defined]
    # half-cell intersections (30 m) no longer count as positive length: no in-band exposure can be credited
    blind = search_route(art, digest, grid=grid, mode="synthetic", hazard_min_intersection_m=hazard)
    assert blind.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert default.route is not None
    ver = verify_route(
        art, digest, default.route, default.route_sha256 or "", "FOUND", grid=grid, mode="synthetic",
        hazard_min_intersection_m=hazard,
    )  # fmt: skip
    assert ver.payload.outcome == "FAIL" and "EXPOSURE_SHORTFALL" in {v.code for v in ver.payload.violations}


def test_energy_defaults_are_the_documented_proposal_when_the_rover_has_no_model(tmp_path: Path) -> None:
    cfg = _config_with(tmp_path, lambda raw: raw["energy_defaults"].__setitem__("science_task_wh", 12))
    inp = design_input(
        "WAYPOINT_RETURN",
        rover_obj=rover("ares-1", energy_model=None),
        mission_obj=mission("mission-mars-mobility"),
        graph=False,
        window_id=catalog.WINDOW_B_CORRIDOR,
    )
    grid = _ramp_window()
    out = design_benchmark(
        inp, mode="synthetic", grid=grid, grid_spec=grid_spec_of(grid),
        defaults=route_defaults_from_config(cfg.algorithms),  # type: ignore[attr-defined]
    )  # fmt: skip
    text = " ".join(out.constraints.limitations)
    assert "science_task_wh=12" in text and "ASSUMED" in text
    default_text = " ".join(_design_no_model(grid).constraints.limitations)
    assert "science_task_wh=10" in default_text
    assert out.constraints_sha256 != _design_no_model(grid).constraints_sha256


def _design_no_model(grid):  # noqa: ANN001, ANN202
    inp = design_input(
        "WAYPOINT_RETURN",
        rover_obj=rover("ares-1", energy_model=None),
        mission_obj=mission("mission-mars-mobility"),
        graph=False,
        window_id=catalog.WINDOW_B_CORRIDOR,
    )
    return design_benchmark(inp, mode="synthetic", grid=grid, grid_spec=grid_spec_of(grid))


@pytest.mark.parametrize("name", ["max_edge_traversals"])
def test_config_keys_exist(name: str) -> None:
    assert hasattr(load_config().algorithms.route_search, name)
