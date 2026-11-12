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


def test_guarded_operator_override_reaches_every_scenario_without_mutating_config():
    from analogforge.application.capabilities import get_scenarios
    from analogforge.settings import Settings

    base = Settings(_env_file=None)
    config_file = base.config_dir / "scenarios.yaml"
    original = config_file.read_bytes()
    defaults = get_scenarios(base)
    effective = get_scenarios(Settings(
        _env_file=None, test_hooks=True,
        operator_limits_json='{"search_max_expansions":1}',
    ))
    for identifier, scenario in effective.items():
        assert scenario["operator_limits"]["search_max_expansions"] == 1
        expected_seconds = defaults[identifier]["operator_limits"]["search_max_seconds"]
        assert scenario["operator_limits"]["search_max_seconds"] == expected_seconds
    assert get_scenarios(base) == defaults
    assert config_file.read_bytes() == original
