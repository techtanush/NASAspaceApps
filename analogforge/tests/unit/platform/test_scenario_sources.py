"""Every scenario characterizes and screens real rasters; the abstract canonical graph is only a PROVE IT fixture.

Found in the Tanush+Ayan trial merge (2026-11-11): with the real science facade, a graph-sourced
CHARACTERIZE_TARGET returns NO_COVERAGE because ``canonical-graph-v1`` has no terrain raster.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from analogforge.ports import catalog

SCENARIOS = yaml.safe_load((Path(__file__).resolve().parents[3] / "config" / "scenarios.yaml").read_text())


def test_terrain_sources_are_never_the_abstract_graph():
    for scenario_id, scenario in SCENARIOS.items():
        for key in ("target_source", "earth_source"):
            source = scenario[key]
            if source is None:  # AWAITING_DATASETS scenarios bind their sources at dataset time
                continue
            assert source.get("fixture_id") != catalog.FIXTURE_CANONICAL_GRAPH, (scenario_id, key)


def test_graph_scenario_keeps_graph_for_prove_it_on_the_mobility_rasters():
    graph = SCENARIOS["synthetic-graph-regression-v1"]
    mobility = SCENARIOS["synthetic-mars-mobility-v1"]
    assert graph["graph_fixture_id"] == catalog.FIXTURE_CANONICAL_GRAPH
    assert graph["target_source"] == mobility["target_source"]
    assert graph["earth_source"] == mobility["earth_source"]
