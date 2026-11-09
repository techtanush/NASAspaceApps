"""SCN-08 support: qualification primitives (thresholds, intervals, confidence, coverage) and the strict,
hash-keyed configuration that policies read."""

from __future__ import annotations

import itertools
import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.science.config import (
    REQUIRED_ADAPTER_IDS,
    ScienceConfig,
    config_for_hash,
    default_config_dir,
    load_config,
)
from analogforge.science.errors import ConfigError, ScienceError
from analogforge.science.features.histogram import SLOPE_HIST_EDGES
from analogforge.science.qualification import (
    RequirementUnderspecifiedError,
    confidence_label,
    evaluate_threshold,
    interval_decision,
    strict_coverage,
)

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


# ----------------------------------------------------------------------------- thresholds
def test_threshold_boundaries_are_inclusive_for_every_operator() -> None:
    assert evaluate_threshold(0.05, "GTE", 0.05, None).meets
    assert not evaluate_threshold(0.0499999999, "GTE", 0.05, None).meets
    assert evaluate_threshold(6.0, "LTE", None, 6.0).meets
    assert not evaluate_threshold(6.0000001, "LTE", None, 6.0).meets
    assert evaluate_threshold(5.0, "BETWEEN", 5.0, 9.0).meets and evaluate_threshold(9.0, "BETWEEN", 5.0, 9.0).meets
    assert evaluate_threshold(4.99, "BETWEEN", 5.0, 9.0).shortfall == "BELOW_LOWER"
    assert evaluate_threshold(9.01, "BETWEEN", 5.0, 9.0).shortfall == "ABOVE_UPPER"
    assert evaluate_threshold(3.0, "EQUALS", 3.0, None).meets
    assert evaluate_threshold(3.1, "EQUALS", 3.0, None).shortfall == "NOT_EQUAL"
    assert evaluate_threshold(3.1, "EQUALS", 3.0, None, tolerance=0.2).meets


def test_tolerance_only_absorbs_numerical_noise_in_the_stated_direction() -> None:
    assert evaluate_threshold(0.05 - 1e-13, "GTE", 0.05, None, tolerance=1e-12).meets
    assert not evaluate_threshold(0.05 - 1e-9, "GTE", 0.05, None, tolerance=1e-12).meets
    assert evaluate_threshold(6.0 + 1e-13, "LTE", None, 6.0, tolerance=1e-12).meets
    assert evaluate_threshold(7.0, "GTE", 5.0, None).shortfall is None


def test_threshold_failure_paths() -> None:
    for operator, lower, upper in (
        ("GTE", None, 1.0),
        ("LTE", 1.0, None),
        ("BETWEEN", 1.0, None),
        ("EQUALS", None, 1.0),
    ):
        with pytest.raises(RequirementUnderspecifiedError):
            evaluate_threshold(1.0, operator, lower, upper)  # type: ignore[arg-type]
    for operator in ("PRESENT", "NOT_NATURALLY_REPRODUCIBLE"):
        with pytest.raises(RequirementUnderspecifiedError):
            evaluate_threshold(1.0, operator, 1.0, 1.0)  # type: ignore[arg-type]
    with pytest.raises(ScienceError):
        evaluate_threshold(float("nan"), "GTE", 1.0, None)  # unknown must stay None, never reach a comparison
    with pytest.raises(ScienceError):
        evaluate_threshold(1.0, "GTE", 1.0, None, tolerance=-1.0)


# ----------------------------------------------------------------------------- interval policy (11 s4)
@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ((5.0, 7.0), "PASS"),
        ((4.0, 7.0), "PASS"),
        ((3.0, 5.0), "UNKNOWN"),
        ((1.0, 3.99), "FAIL"),
        ((2.0, 4.0), "UNKNOWN"),
    ],
)
def test_lower_bound_interval_rule(interval: tuple[float, float], expected: str) -> None:
    assert interval_decision("GTE", 4.0, None, *interval) == expected


@pytest.mark.parametrize(
    ("interval", "expected"),
    [((1.0, 6.0), "PASS"), ((1.0, 6.5), "UNKNOWN"), ((6.01, 9.0), "FAIL"), ((6.0, 9.0), "UNKNOWN")],
)
def test_upper_bound_interval_rule(interval: tuple[float, float], expected: str) -> None:
    assert interval_decision("LTE", None, 6.0, *interval) == expected


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ((5.0, 9.0), "PASS"),
        ((6.0, 8.0), "PASS"),
        ((4.0, 6.0), "UNKNOWN"),
        ((8.0, 10.0), "UNKNOWN"),
        ((1.0, 4.9), "FAIL"),
        ((9.1, 12.0), "FAIL"),
    ],
)
def test_range_interval_rule(interval: tuple[float, float], expected: str) -> None:
    assert interval_decision("BETWEEN", 5.0, 9.0, *interval) == expected


def test_interval_failure_paths() -> None:
    with pytest.raises(ScienceError):
        interval_decision("GTE", 1.0, None, 3.0, 2.0)
    with pytest.raises(ScienceError):
        interval_decision("GTE", 1.0, None, float("nan"), 2.0)
    with pytest.raises(RequirementUnderspecifiedError):
        interval_decision("GTE", None, None, 1.0, 2.0)
    with pytest.raises(RequirementUnderspecifiedError):
        interval_decision("PRESENT", None, None, 1.0, 2.0)


# ----------------------------------------------------------------------------- confidence rubric
def test_confidence_levels_follow_the_rubric() -> None:
    strong = {"adequate": True, "direct_evidence": True, "coverage": 0.95}
    assert confidence_label(**strong, uncertainty="not_quantified") == "MEDIUM"  # nominal model: at most MEDIUM
    assert confidence_label(**strong, uncertainty="bounded_sensitivity") == "MEDIUM"
    assert confidence_label(**strong, uncertainty="quantified") == "HIGH"
    assert confidence_label(**strong, uncertainty="quantified", assumed_parameters=True) == "LOW"
    assert confidence_label(adequate=True, direct_evidence=True, coverage=0.89, uncertainty="quantified") == "LOW"
    assert (
        confidence_label(adequate=True, direct_evidence=True, coverage=0.90, uncertainty="not_quantified") == "MEDIUM"
    )
    assert confidence_label(adequate=True, direct_evidence=True, coverage=None, uncertainty="quantified") == "LOW"
    assert confidence_label(adequate=False, direct_evidence=True, coverage=1.0, uncertainty="quantified") == "LOW"
    assert confidence_label(adequate=True, direct_evidence=False, coverage=1.0, uncertainty="quantified") == "LOW"
    assert (
        confidence_label(**strong, uncertainty="not_quantified", medium_min_coverage=0.99) == "LOW"
    )  # configurable floor


def test_confidence_is_never_unassessed_and_never_high_without_quantified_uncertainty() -> None:
    for adequate, direct, coverage, uncertainty, assumed in itertools.product(
        (True, False),
        (True, False),
        (None, 0.0, 0.5, 0.9, 1.0),
        ("quantified", "bounded_sensitivity", "not_quantified"),
        (True, False),
    ):
        label = confidence_label(
            adequate=adequate,
            direct_evidence=direct,
            coverage=coverage,
            uncertainty=uncertainty,
            assumed_parameters=assumed,
        )  # type: ignore[arg-type]
        assert label in ("HIGH", "MEDIUM", "LOW")
        if label == "HIGH":
            assert uncertainty == "quantified" and adequate and direct and not assumed and coverage is not None


# ----------------------------------------------------------------------------- strict coverage
def test_strict_coverage_keeps_unknown_in_the_denominator_and_reports_gaps_separately() -> None:
    cov = strict_coverage([("PASS", 1.0), ("UNKNOWN", 1.0), ("GAP", 1.0), ("FAIL", 2.0), ("PARTIAL", 1.0)])
    assert (cov.passed_weight, cov.reproducible_weight, cov.gap_weight) == (1.0, 5.0, 1.0)
    assert cov.value == pytest.approx(0.2)
    improved = strict_coverage([("PASS", 1.0), ("PASS", 1.0), ("GAP", 1.0), ("FAIL", 2.0), ("PARTIAL", 1.0)])
    assert improved.value == pytest.approx(0.4)  # perturbation: a pass raises coverage; PARTIAL is never counted as 0.5
    assert strict_coverage([("GAP", 3.0)]).value is None  # nothing reproducible -> no coverage number
    assert strict_coverage([]).value is None
    with pytest.raises(ScienceError):
        strict_coverage([("PASS", 0.0)])
    with pytest.raises(ScienceError):
        strict_coverage([("PASS", float("nan"))])


# ----------------------------------------------------------------------------- configuration
def test_default_config_loads_completely_and_is_immutable() -> None:
    config = load_config()
    assert default_config_dir() == REAL_CONFIG_DIR.resolve()
    assert set(config.algorithms.observable_policies) >= set(catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.values())
    for algorithm_id in (v for v in catalog.ALGORITHM_IDS.values() if v != "scientific-assurance"):
        assert config.algorithm_version(algorithm_id)
    assert {catalog.MEASUREMENT_SPEC_TARGET, catalog.MEASUREMENT_SPEC_EARTH} <= set(config.algorithms.measurement_specs)
    assert set(REQUIRED_ADAPTER_IDS) <= set(config.datasets.adapters)
    assert config.candidates.reference_sets[catalog.REFERENCE_SET_PRACTICE].entries
    with pytest.raises(ValidationError):
        config.algorithms.thresholds.default_cap_deg = 99.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        config.algorithms.observable_policies["route-reserve-v1"].min_valid_fraction = 0.0  # type: ignore[misc]


def test_config_is_keyed_by_the_canonical_hash_of_the_parsed_yaml() -> None:
    config = load_config()
    parsed = yaml.safe_load((REAL_CONFIG_DIR / "algorithms.yaml").read_text())
    assert config.algorithm_config_sha256 == canonical_sha256(parsed)
    assert load_config() is config and load_config(REAL_CONFIG_DIR) is config  # parsed once, cached by content hash
    assert config_for_hash(config.algorithm_config_sha256) is config
    assert config_for_hash("0" * 64) is None
    assert config.verify_pin(None) and config.verify_pin(config.algorithm_config_sha256)
    assert not config.verify_pin("f" * 64)
    with pytest.raises(ConfigError):
        config.algorithm_version("not-an-algorithm")
    with pytest.raises(ConfigError):
        config.measurement_spec("terrain-moon-v9")


def test_config_values_match_the_kit_catalog_and_architecture() -> None:
    config = load_config()
    alg = config.algorithms
    assert (
        alg.grid.cell_size_m == catalog.PRACTICE_GRID_CELL_M and alg.grid.window_cells == catalog.PRACTICE_WINDOW_CELLS
    )
    route = alg.route_search
    assert (route.max_expansions, route.max_seconds, route.max_labels_per_node, route.max_edge_traversals) == (
        catalog.BUDGETS["search_max_expansions"],
        catalog.BUDGETS["search_max_seconds"],
        catalog.BUDGETS["search_max_labels_per_node"],
        catalog.BUDGETS["max_undirected_edge_traversals"],
    )
    energy = alg.energy_defaults
    assert (energy.rolling_coefficient, energy.drive_efficiency, energy.idle_power_w, energy.science_task_wh) == (
        0.06,
        0.65,
        35,
        10,
    )
    assert (energy.uncertainty_fraction, energy.calibration_status, energy.gravity_mps2) == (0.25, "ASSUMED", 9.80665)
    assert alg.design_defaults.max_route_m == 8000 and alg.design_defaults.task_dwell_s == 60
    assert alg.thresholds.default_cap_deg == 18 and alg.thresholds.min_valid_fraction == 0.80
    assert alg.fixtures.seed == 20261105
    assert alg.measurement_specs[catalog.MEASUREMENT_SPEC_TARGET].slope_hist_edges_deg == SLOPE_HIST_EDGES
    assert alg.measurement_specs[catalog.MEASUREMENT_SPEC_EARTH].roughness_windows_cells == (3, 5, 9)
    for pid, policy in alg.observable_policies.items():
        assert policy.min_valid_fraction == 0.80, pid
        assert all(
            g in {"SC-02", "SC-03", "SC-04", "SC-05", "SC-06", "SC-07", "SC-08", "SC-09", "SC-10", "SC-11", "SC-13"}
            for g in policy.applicable_gates
        )
    practice = config.candidates.search_region_sets[catalog.SEARCH_REGION_PRACTICE]
    assert (practice.crs_epsg, practice.sw_easting_m, practice.north_northing_m) == (
        catalog.PRACTICE_GRID_CRS_EPSG,
        catalog.PRACTICE_GRID_SW_EASTING_M,
        catalog.PRACTICE_GRID_NORTH_NORTHING_M,
    )
    assert (practice.rows, practice.cols, len(practice.windows)) == (3, 3, 9)
    assert [w.window_id for w in practice.windows if w.negative_control] == [catalog.WINDOW_C_FLAT]
    known = config.candidates.reference_sets[catalog.REFERENCE_SET_PRACTICE].entries
    assert [e.window_id for e in known] == [catalog.WINDOW_KNOWN_REFERENCE] and known[0].synthetic
    assert config.datasets.adapters["synthetic_practice"].network_required is False


def _copy_config(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(REAL_CONFIG_DIR, target)
    return target


def _edit(path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_changing_any_value_changes_the_algorithm_hash(tmp_path: Path) -> None:
    base = load_config()
    copy = _copy_config(tmp_path)
    assert load_config(copy).algorithm_config_sha256 == base.algorithm_config_sha256  # same content, same identity
    _edit(copy / "algorithms.yaml", lambda d: d["thresholds"].update(default_cap_deg=17))
    changed = load_config(copy)
    assert (
        changed.algorithm_config_sha256 != base.algorithm_config_sha256
        and changed.algorithms.thresholds.default_cap_deg == 17
    )
    assert config_for_hash(changed.algorithm_config_sha256) is changed


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(surprise_key=1),  # unknown top-level key
        lambda d: d["thresholds"].update(surprise=1),  # unknown nested key
        lambda d: d["observable_policies"].pop("route-reserve-v1"),  # a catalog policy is missing
        lambda d: d["algorithm_lock"].pop("verify-route"),  # an emitted algorithm has no version
        lambda d: d["measurement_specs"].pop("terrain-earth-v1"),
        lambda d: d["energy_defaults"].update(gravity_mps2=3.71),  # Earth gravity only
        lambda d: d["energy_defaults"].update(drive_efficiency=1.5),
        lambda d: d["measurement_specs"]["terrain-earth-v1"]["comparison_support"].update(allow_upsample=True),
        lambda d: d["measurement_specs"]["terrain-earth-v1"].update(roughness_windows_cells=[3, 4]),
        lambda d: d["observable_policies"]["thermal-min-v1"].update(applicable_gates=["SC-99"]),
        lambda d: d["observable_policies"]["thermal-min-v1"].update(min_valid_fraction=1.5),
        lambda d: d["thresholds"].update(default_cap_deg=95),
        lambda d: d["grid"].update(cell_size_m=0),
    ],
)
def test_algorithms_yaml_is_validated_strictly(tmp_path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    copy = _copy_config(tmp_path)
    _edit(copy / "algorithms.yaml", mutate)
    with pytest.raises(ConfigError):
        load_config(copy)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["search_region_sets"].pop("practice-earth-grid-v1"),
        lambda d: d["reference_sets"].pop("practice-reference-set-v1"),
        lambda d: d["search_region_sets"]["practice-earth-grid-v1"]["windows"].pop(),  # grid no longer rows x cols
        lambda d: d["search_region_sets"]["practice-earth-grid-v1"]["windows"][0].update(window_id="grid-r9c9"),
        lambda d: d["search_region_sets"]["practice-earth-grid-v1"].pop("crs_epsg"),
        lambda d: d["reference_sets"]["practice-reference-set-v1"]["entries"][0].update(
            synthetic=False
        ),  # real needs a URL
        lambda d: d["reference_sets"]["practice-reference-set-v1"]["entries"][0].update(
            georeference_quality="SURVEYED"
        ),
        lambda d: d["search_region_sets"]["local-dataset-grid-v1"].pop("order"),
    ],
)
def test_candidates_yaml_is_validated_strictly(tmp_path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    copy = _copy_config(tmp_path)
    _edit(copy / "candidates.yaml", mutate)
    with pytest.raises(ConfigError):
        load_config(copy)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["adapters"].pop("moon_lola_gdr"),
        lambda d: d["adapters"]["local_dataset"].update(network_required=True),
        lambda d: d["adapters"]["mars_mola_megdr"].update(authentication="TOKEN_IN_URL"),
        lambda d: d["adapters"]["earth_user_survey"].pop("decoder"),
    ],
)
def test_datasets_yaml_is_validated_strictly(tmp_path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
    copy = _copy_config(tmp_path)
    _edit(copy / "datasets.yaml", mutate)
    with pytest.raises(ConfigError):
        load_config(copy)


def test_missing_or_malformed_files_are_config_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nowhere")
    copy = _copy_config(tmp_path)
    (copy / "algorithms.yaml").write_text("key: [unterminated")
    with pytest.raises(ConfigError):
        load_config(copy)
    (copy / "algorithms.yaml").write_text("- a\n- b\n")
    with pytest.raises(ConfigError):
        load_config(copy)
    (copy / "algorithms.yaml").write_text("thresholds: {x: .nan}\n")
    with pytest.raises(ConfigError):
        load_config(copy)


def test_policy_lookup_returns_none_for_unknown_ids() -> None:
    config: ScienceConfig = load_config()
    assert config.policy("slope-band-area-fraction-v1") is not None
    assert config.policy("slope-band-area-fraction-v2") is None
