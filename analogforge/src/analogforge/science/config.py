"""Strict, immutable configuration for the science library.

``config/algorithms.yaml``, ``config/candidates.yaml`` and ``config/datasets.yaml`` are parsed once into frozen
pydantic models (unknown keys are rejected) and cached under the content hashes of the files.  The platform pins
``algorithm_config_sha256 = canonical_sha256(parsed algorithms.yaml)``; :meth:`ScienceConfig.verify_pin` checks it.

No environment access: the default config directory is located relative to this file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.science.errors import ConfigError

GateId = Literal[
    "SC-01", "SC-02", "SC-03", "SC-04", "SC-05", "SC-06", "SC-07", "SC-08",
    "SC-09", "SC-10", "SC-11", "SC-12", "SC-13", "SC-14", "SC-15",
]  # fmt: skip
BodyName = Literal["EARTH", "MOON", "MARS"]

# Algorithm ids that the platform (not science) emits.
_PLATFORM_ALGORITHM_IDS = frozenset({catalog.ALGORITHM_IDS["SCIENTIFIC_ASSURANCE"]})
# Algorithm ids that science emits besides ports.catalog.ALGORITHM_IDS.
REQUIRED_EXTRA_ALGORITHM_IDS = (
    "build-display-layers",
    "resolve-coverage",
    "fetch-source",
    "exhaustive-subset-v1",
    "auto-waypoints-v1",
    "earth-simple-v1",
    "slope-lsq-plane-3x3-v1",
    "roughness-detrended-rms-v1",
    "relief-robust-q05-q95-v1",
    "slope-w1-binned-v1",
    "analysis-grid-npz-v1",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# --------------------------------------------------------------------------- algorithms.yaml
class ComparisonSupportRule(_Strict):
    rule: Literal["MAX_OF_NATIVE_AND_REQUESTED"]
    aggregation: Literal["AREA_AVERAGE"]
    allow_upsample: Literal[False]
    default_requested_m: float | None = Field(default=None, gt=0)


class MeasurementSpec(_Strict):
    derivative_window_cells: Literal[3]
    roughness_windows_cells: tuple[int, ...] = Field(min_length=1)
    slope_hist_edges_deg: tuple[float, ...] = Field(min_length=2)
    comparison_support: ComparisonSupportRule

    @model_validator(mode="after")
    def _check(self) -> MeasurementSpec:
        if any(w < 3 or w % 2 == 0 for w in self.roughness_windows_cells):
            raise ValueError("roughness windows must be odd cell counts >= 3")
        edges = self.slope_hist_edges_deg
        if any(b <= a for a, b in zip(edges, edges[1:], strict=False)):
            raise ValueError("slope_hist_edges_deg must be strictly ascending")
        return self


class ObservablePolicy(_Strict):
    observable: str
    quantity: str
    units: str
    valid_bodies: tuple[BodyName, ...] = Field(min_length=1)
    support_rule: Literal["REQUIREMENT_WINDOW", "NOT_APPLICABLE"]
    coverage_denominator: Literal[
        "VALID_LAND_AREA_OVER_WINDOW_AREA",
        "VALID_RETRIEVAL_AREA_OVER_WINDOW_AREA",
        "VALID_AREA_OVER_WINDOW_AREA",
        "ROUTE_LENGTH",
        "NOT_APPLICABLE",
    ]
    min_valid_fraction: float = Field(ge=0, le=1)
    temporal_support: Literal["NOT_TIME_DEPENDENT", "UNRESOLVED"]
    proxy_policy: Literal["DIRECT_ONLY", "NO_PROXY_ACCEPTED"]
    decision_rule: Literal[
        "NOMINAL_THRESHOLD_INCLUSIVE",
        "ROUTE_VERIFIER_BENCHMARK",
        "UNRESOLVED_NO_RULE",
        "SCALE_GATE_ONLY",
        "PHYSICAL_GAP",
    ]
    tolerance: float = Field(ge=0)
    applicable_gates: tuple[GateId, ...] = Field(min_length=1)


class GridConfig(_Strict):
    class TargetSupport(_Strict):
        rule: Literal["MAX_OF_NATIVE_AND_REQUESTED"]
        earth_default_m: float = Field(gt=0)
        aggregation: Literal["AREA_AVERAGE"]
        allow_upsample: Literal[False]

    cell_size_m: float = Field(gt=0)
    window_cells: int = Field(ge=3)
    target_support_m: TargetSupport


class RouteSearchConfig(_Strict):
    max_expansions: int = Field(ge=1)
    max_seconds: float = Field(gt=0)
    max_labels_per_node: int = Field(ge=1)
    max_edge_traversals: int = Field(ge=1)


class EnergyDefaults(_Strict):
    model_id: Literal["earth-simple-v1"]
    rolling_coefficient: float = Field(ge=0, le=1)
    drive_efficiency: float = Field(gt=0, le=1)
    idle_power_w: float = Field(ge=0)
    science_task_wh: float = Field(ge=0)
    roughness_multiplier: float = Field(ge=1)
    uncertainty_fraction: float = Field(ge=0, le=1)
    calibration_status: Literal["ASSUMED", "CALIBRATED"]
    gravity_mps2: float

    @model_validator(mode="after")
    def _earth_gravity_only(self) -> EnergyDefaults:
        if self.gravity_mps2 != 9.80665:
            raise ValueError("the Earth field-test energy model uses 9.80665 m/s^2 only")
        return self


class AutoWaypoints(_Strict):
    rule_id: Literal["auto-waypoints-v1"]
    w1_min_edge_fraction: float = Field(gt=0)
    w1_max_edge_fraction: float = Field(gt=0)
    w2_min_from_w1_edge_fraction: float = Field(gt=0)
    band_neighbourhood_cells: int = Field(ge=1)
    tolerance_cells: float = Field(ge=0)


class DesignDefaults(_Strict):
    max_route_m: float = Field(gt=0)
    task_dwell_s: float = Field(ge=0)
    footprint_dilation_m: float = Field(ge=0)
    science_task_required_capability: str = Field(min_length=1)
    auto_waypoints: AutoWaypoints


class Thresholds(_Strict):
    default_cap_deg: float = Field(gt=0, lt=90)
    min_valid_fraction: float = Field(ge=0, le=1)
    hard_block_valid_fraction: float = Field(ge=0, le=1)
    water_only_fraction: float = Field(gt=0, le=1)
    medium_confidence_min_coverage: float = Field(ge=0, le=1)
    flat_gradient_tolerance: float = Field(ge=0)
    hazard_min_intersection_m: float = Field(ge=0)
    numeric_tolerance: float = Field(ge=0)
    energy_tolerance_wh: float = Field(ge=0)
    max_linear_distortion: float = Field(gt=0, lt=1)


class GeneratorSpec(_Strict):
    generator_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class FixturesConfig(_Strict):
    seed: int = Field(ge=0)
    generators: dict[str, GeneratorSpec]


class AlgorithmsConfig(_Strict):
    config_version: Literal["1.0"]
    algorithm_lock: dict[str, str]
    measurement_specs: dict[str, MeasurementSpec]
    observable_policies: dict[str, ObservablePolicy]
    grid: GridConfig
    route_search: RouteSearchConfig
    energy_defaults: EnergyDefaults
    design_defaults: DesignDefaults
    thresholds: Thresholds
    fixtures: FixturesConfig

    @model_validator(mode="after")
    def _complete(self) -> AlgorithmsConfig:
        required_ids = {v for v in catalog.ALGORITHM_IDS.values() if v not in _PLATFORM_ALGORITHM_IDS}
        required_ids |= set(REQUIRED_EXTRA_ALGORITHM_IDS)
        missing = sorted(required_ids - set(self.algorithm_lock))
        if missing:
            raise ValueError(f"algorithm_lock lacks versions for: {missing}")
        for spec_id in (catalog.MEASUREMENT_SPEC_TARGET, catalog.MEASUREMENT_SPEC_EARTH):
            if spec_id not in self.measurement_specs:
                raise ValueError(f"measurement_specs lacks {spec_id}")
        earth_default = self.measurement_specs[catalog.MEASUREMENT_SPEC_EARTH].comparison_support.default_requested_m
        if earth_default != self.grid.target_support_m.earth_default_m:
            raise ValueError(
                f"grid.target_support_m.earth_default_m ({self.grid.target_support_m.earth_default_m}) must equal "
                f"measurement_specs.{catalog.MEASUREMENT_SPEC_EARTH}.comparison_support.default_requested_m "
                f"({earth_default})"
            )
        needed = sorted(set(catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.values()) - set(self.observable_policies))
        if needed:
            raise ValueError(f"observable_policies lacks policies: {needed}")
        return self


# --------------------------------------------------------------------------- candidates.yaml
class WindowEntry(_Strict):
    window_id: str = Field(min_length=1)
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    negative_control: bool = False


class SearchRegionSet(_Strict):
    description: str
    kind: Literal["FIXED_GRID", "GENERATED_GRID"]
    body: Literal["EARTH"]
    cell_size_m: float = Field(gt=0)
    window_cells: int = Field(ge=3)
    id_pattern: str
    coarse_windows_max: int = Field(ge=1)
    # FIXED_GRID
    crs_epsg: int | None = None
    sw_easting_m: float | None = None
    north_northing_m: float | None = None
    rows: int | None = Field(default=None, ge=1)
    cols: int | None = Field(default=None, ge=1)
    windows: tuple[WindowEntry, ...] = ()
    # GENERATED_GRID
    order: Literal["NW_ROW_MAJOR"] | None = None
    negative_control_window_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _kind(self) -> SearchRegionSet:
        if self.kind == "FIXED_GRID":
            required = (self.crs_epsg, self.sw_easting_m, self.north_northing_m, self.rows, self.cols)
            if any(v is None for v in required) or not self.windows:
                raise ValueError("FIXED_GRID needs crs_epsg, sw_easting_m, north_northing_m, rows, cols and windows")
            ids = [w.window_id for w in self.windows]
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate window_id in FIXED_GRID")
            assert self.rows is not None and self.cols is not None
            if self.rows * self.cols != len(self.windows):
                raise ValueError("FIXED_GRID windows must cover rows x cols exactly")
            for w in self.windows:
                if w.window_id != self.id_pattern.format(row=w.row, col=w.col):
                    raise ValueError(f"window {w.window_id} does not follow id_pattern")
                if w.row >= self.rows or w.col >= self.cols:
                    raise ValueError(f"window {w.window_id} lies outside the grid")
        elif self.order is None:
            raise ValueError("GENERATED_GRID needs order")
        return self


class ReferenceEntry(_Strict):
    entry_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    relation: Literal["KNOWN_ANALOG"]
    synthetic: bool
    mission_question: str
    citation: str = Field(min_length=1)
    citation_url: str | None
    georeference_quality: Literal["SYNTHETIC", "SURVEYED", "APPROXIMATE", "UNVERIFIED"]

    @model_validator(mode="after")
    def _real_needs_url(self) -> ReferenceEntry:
        if not self.synthetic and not self.citation_url:
            raise ValueError("real reference entries need a citation_url")
        if self.synthetic and self.georeference_quality != "SYNTHETIC":
            raise ValueError("synthetic reference entries use georeference_quality SYNTHETIC")
        return self


class ReferenceSet(_Strict):
    version: str
    description: str
    entries: tuple[ReferenceEntry, ...]


class CandidatesConfig(_Strict):
    config_version: Literal["1.0"]
    search_region_sets: dict[str, SearchRegionSet]
    reference_sets: dict[str, ReferenceSet]

    @model_validator(mode="after")
    def _required(self) -> CandidatesConfig:
        if catalog.SEARCH_REGION_PRACTICE not in self.search_region_sets:
            raise ValueError(f"search_region_sets lacks {catalog.SEARCH_REGION_PRACTICE}")
        if catalog.REFERENCE_SET_PRACTICE not in self.reference_sets:
            raise ValueError(f"reference_sets lacks {catalog.REFERENCE_SET_PRACTICE}")
        return self


# --------------------------------------------------------------------------- datasets.yaml
REQUIRED_ADAPTER_IDS = (
    "earth_nasadem_hgt_v001",
    "earth_srtmgl1_v003",
    "mars_mola_megdr",
    "moon_lola_gdr",
    "earth_emit_l2bmin_v001",
    "moon_diviner_derived",
    "earth_user_survey",
    "local_dataset",
    "synthetic_practice",
)


class AdapterEntry(_Strict):
    version: str
    body: BodyName | None
    provider: str
    kind: Literal["NETWORK", "LOCAL", "SYNTHETIC"]
    discovery_method: str
    product_families: tuple[str, ...]
    documentation_urls: tuple[str, ...]
    authentication: Literal["NONE", "EARTHDATA_BEARER"]
    expected_metadata: tuple[str, ...]
    decoder: str
    quality_mask_builder: str
    permitted_claim_types: tuple[str, ...]
    network_required: bool


class DatasetsConfig(_Strict):
    config_version: Literal["1.0"]
    adapters: dict[str, AdapterEntry]

    @model_validator(mode="after")
    def _required(self) -> DatasetsConfig:
        missing = [a for a in REQUIRED_ADAPTER_IDS if a not in self.adapters]
        if missing:
            raise ValueError(f"adapters lacks: {missing}")
        for adapter_id, entry in self.adapters.items():
            if entry.kind != "NETWORK" and entry.network_required:
                raise ValueError(f"{adapter_id}: non-network adapter cannot require network")
        return self


# --------------------------------------------------------------------------- aggregate
class ScienceConfig(_Strict):
    """Everything the science library reads from ``config/*.yaml``."""

    algorithms: AlgorithmsConfig
    candidates: CandidatesConfig
    datasets: DatasetsConfig
    algorithm_config_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidates_config_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    datasets_config_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def policy(self, policy_id: str) -> ObservablePolicy | None:
        """Observable policy by id, or ``None`` when unknown (callers must then answer UNKNOWN)."""
        return self.algorithms.observable_policies.get(policy_id)

    def policy_sha256(self, policy_id: str) -> str | None:
        policy = self.policy(policy_id)
        if policy is None:
            return None
        return canonical_sha256({"policy_id": policy_id, "policy": policy.model_dump(mode="json")})

    def algorithm_version(self, algorithm_id: str) -> str:
        try:
            return self.algorithms.algorithm_lock[algorithm_id]
        except KeyError as exc:
            raise ConfigError(f"algorithm {algorithm_id!r} is not in algorithm_lock") from exc

    def measurement_spec(self, spec_id: str) -> MeasurementSpec:
        try:
            return self.algorithms.measurement_specs[spec_id]
        except KeyError as exc:
            raise ConfigError(f"unknown measurement_spec_id {spec_id!r}") from exc

    def verify_pin(self, pinned_sha256: str | None) -> bool:
        """True when no pin was supplied or the pin equals this configuration's algorithm hash."""
        return pinned_sha256 is None or pinned_sha256 == self.algorithm_config_sha256


def default_config_dir() -> Path:
    """``analogforge/config`` located relative to this file (no environment lookup)."""
    return Path(__file__).resolve().parents[3] / "config"


_CACHE: dict[tuple[str, str, str], ScienceConfig] = {}
_BY_ALGORITHM_HASH: dict[str, ScienceConfig] = {}
_LOCK = Lock()


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path.name}: {exc.strerror}") from exc
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"{path.name} must contain a mapping at the top level")
    return parsed


def load_config(config_dir: Path | None = None) -> ScienceConfig:
    """Parse the three YAML files strictly and return the cached immutable configuration."""
    directory = (config_dir if config_dir is not None else default_config_dir()).resolve()
    algorithms_raw = _read_yaml(directory / "algorithms.yaml")
    candidates_raw = _read_yaml(directory / "candidates.yaml")
    datasets_raw = _read_yaml(directory / "datasets.yaml")
    try:
        key = (
            canonical_sha256(algorithms_raw),
            canonical_sha256(candidates_raw),
            canonical_sha256(datasets_raw),
        )
    except ValueError as exc:
        raise ConfigError(f"configuration contains a non-finite or non-JSON value: {exc}") from exc
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        try:
            config = ScienceConfig(
                algorithms=AlgorithmsConfig.model_validate(algorithms_raw),
                candidates=CandidatesConfig.model_validate(candidates_raw),
                datasets=DatasetsConfig.model_validate(datasets_raw),
                algorithm_config_sha256=key[0],
                candidates_config_sha256=key[1],
                datasets_config_sha256=key[2],
            )
        except ValueError as exc:  # pydantic.ValidationError is a ValueError
            raise ConfigError(f"configuration in {directory} is invalid: {exc}") from exc
        _CACHE[key] = config
        _BY_ALGORITHM_HASH[key[0]] = config
        return config


@lru_cache(maxsize=1)
def default_thresholds() -> Thresholds:
    """``thresholds`` of the repository's own ``algorithms.yaml`` (cached) for pure helpers without a config handle."""
    return load_config().algorithms.thresholds


def config_for_hash(algorithm_config_sha256: str) -> ScienceConfig | None:
    """The already-loaded configuration whose ``algorithm_config_sha256`` equals the argument, if any."""
    with _LOCK:
        return _BY_ALGORITHM_HASH.get(algorithm_config_sha256)
