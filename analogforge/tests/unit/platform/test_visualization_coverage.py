"""Coverage is source catalog metadata, never a global texture or a science verdict."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml
from pyproj import CRS

from analogforge.api.errors import ApiError
from analogforge.application import datasets
from analogforge.application import visualization_coverage as coverage
from analogforge.ports.hashing import canonical_sha256, file_sha256
from analogforge.ports.science import ScienceComputationResult, ScienceOperation
from analogforge.ports.science_payloads import IngestLocalDatasetPayload, ValidationCheck
from analogforge.settings import Settings

SCENARIO = "live-hackathon-v1"
POLICY = "test-coverage-v1"


@pytest.fixture
def configured(tmp_path, monkeypatch):
    config = tmp_path / "config"
    shutil.copytree(Settings(_env_file=None).config_dir, config)
    settings = Settings(_env_file=None, data_root=tmp_path / "data", config_dir=config)
    selected = []
    for dataset_id, body, role in (
        ("test-mars-source", "MARS", "TARGET_TERRAIN"),
        ("test-earth-source", "EARTH", "EARTH_TERRAIN"),
    ):
        root = settings.data_root / "incoming" / dataset_id
        root.mkdir(parents=True)
        (root / "terrain.tif").write_bytes(b"unit fixture; not a raster")
        manifest = {
            "dataset_id": dataset_id,
            "title": "Unit fixture",
            "provider": "NASA PDS",
            "is_synthetic": False,
            "body": body,
            "role": role,
            "format": "GEOTIFF",
            "files": [{"path": "terrain.tif", "sha256": file_sha256(root / "terrain.tif")}],
            "primary_file": "terrain.tif",
            "quantity": "ELEVATION",
            "units": "m",
            "vertical_reference": "Declared test reference",
            "crs": {"epsg": 4326}
            if body == "EARTH"
            else {"wkt": CRS.from_proj4("+proj=longlat +R=3396190 +type=crs").to_wkt()},
            "longitude_convention": "NEG180_180",
            "longitude_direction": "POSITIVE_EAST",
            "latitude_type": "GEODETIC" if body == "EARTH" else "PLANETOCENTRIC",
            "declared_native_resolution_m": 30,
            "license_note": "Test",
            "citation": "Test",
            "product_identity": {"version": "test-v1"},
        }
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest))
        parsed = datasets.load_manifest(settings, dataset_id)
        report = {
            "dataset_id": dataset_id,
            "status": "PASS",
            "manifest_sha256": canonical_sha256(parsed),
            "usable_for_quantitative_claims": True,
            "checks": [{"check_id": "manifest_schema", "status": "PASS"}],
        }
        validation = settings.data_root / "validation" / f"{dataset_id}.json"
        validation.parent.mkdir(exist_ok=True)
        validation.write_text(json.dumps(report))
        selected.append(dataset_id)
    datasets.create_lock(settings, POLICY, selected)
    path = config / "scenarios.yaml"
    scenarios = yaml.safe_load(path.read_text())
    scenario = scenarios[SCENARIO]
    scenario.update(
        status="AVAILABLE",
        allowed_modes=["live"],
        default_dataset_lock_id=POLICY,
        target_source={"kind": "LOCAL_DATASET", "dataset_id": selected[0]},
        earth_source={"kind": "LOCAL_DATASET", "dataset_id": selected[1]},
    )
    path.write_text(yaml.safe_dump(scenarios))

    class Science:
        def supported_operations(self):
            return {ScienceOperation.INGEST_LOCAL_DATASET}

        def execute(self, request, context):
            assert request.source_policy.allow_network is False
            assert context.http_client() is None
            manifest = request.inputs.manifest
            return ScienceComputationResult(
                request_id=request.request_id,
                operation=request.operation,
                mode=request.mode,
                status="SUCCEEDED",
                algorithm_id="ingest-local-dataset",
                algorithm_version="unit",
                parameters_sha256="0" * 64,
                input_sha256=canonical_sha256(request),
                payload=IngestLocalDatasetPayload(
                    dataset_id=manifest.dataset_id,
                    body=manifest.body,
                    role=manifest.role,
                    usable_for_quantitative_claims=True,
                    normalized_evidence=None,
                    checks=[ValidationCheck(check_id="transform_sane", status="PASS", message="Test")],
                    native_resolution_m=30.5,
                    bbox_lonlat=(1, 2, 3, 4),
                ),
            )

    monkeypatch.setattr(coverage, "_entrypoint", lambda *_: lambda **__: Science())
    return settings


def _get(settings, **overrides):
    options = dict(body="MARS", bbox=(1.2, 2.2, 2.8, 3.8), scenario_config_id=SCENARIO, dataset_lock_id=POLICY)
    return coverage.get_visualization_coverage(settings, **(options | overrides))


def _index(settings):
    return settings.data_root / "visualization" / "coverage" / f"{POLICY}.json"


@pytest.mark.parametrize(
    ("bbox", "expected"),
    [((1.2, 2.2, 2.8, 3.8), "COVERED"), ((0, 2, 2, 3), "PARTIAL"), ((4, 2, 5, 3), "NONE"), ((3, 2, 4, 3), "NONE")],
)
def test_coverage_states_are_locked_footprint_only(configured, bbox, expected):
    summary = coverage.prepare_visualization_coverage(configured, POLICY)
    assert summary["status"] == "PASS" and summary["footprints"] == 2
    response = _get(configured, bbox=bbox)
    assert response.state == expected
    assert response.basis == "VALIDATED_FOOTPRINT"
    assert len(response.datasets) == 1
    assert response.datasets[0].id == "test-mars-source"
    assert response.datasets[0].native_resolution_m == 30.5  # Actual intake, not declared 30.
    assert response.datasets[0].comparison_support_m is None
    assert "does not establish" in response.reason
    schema = Path(__file__).resolve().parents[4] / "team handoffs/ui-split/schemas/coverage.v1.schema.json"
    jsonschema.validate(response.model_dump(mode="json"), json.loads(schema.read_text()))
    assert str(configured.data_root) not in response.model_dump_json()


def test_get_never_executes_science_hashes_source_bytes_or_writes(configured, monkeypatch):
    coverage.prepare_visualization_coverage(configured, POLICY)
    files = {path: path.read_bytes() for path in configured.data_root.rglob("*") if path.is_file()}
    original_open = Path.open

    def checked_open(path, *args, **kwargs):
        assert path.suffix != ".tif", "HTTP must not reopen raster bytes"
        mode = args[0] if args else kwargs.get("mode", "r")
        assert not any(flag in mode for flag in "wa+")
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("HTTP must not execute science or hash source bytes")

    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(coverage, "_entrypoint", forbidden)
    monkeypatch.setattr(datasets, "file_sha256", forbidden)
    assert _get(configured).state == "COVERED"
    monkeypatch.undo()
    assert all(path.read_bytes() == data for path, data in files.items())


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "source-same-time",
        "manifest",
        "validation",
        "index",
        "lock",
        "config",
        "missing-index",
        "wrong-lock-index",
        "source-symlink",
    ],
)
def test_changed_or_missing_inputs_fail_closed_without_paths(configured, change):
    coverage.prepare_visualization_coverage(configured, POLICY)
    root = configured.data_root
    path = root / "incoming/test-mars-source/terrain.tif"
    if change.startswith("source"):
        info = path.stat()
        if change == "source-symlink":
            foreign = root.parent / "foreign-secret.tif"
            foreign.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(foreign)
        else:
            path.write_bytes(b"X" * info.st_size)
            if change == "source-same-time":
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    elif change == "manifest":
        path = path.with_name("manifest.yaml")
        raw = yaml.safe_load(path.read_text())
        raw["title"] = "Changed"
        path.write_text(yaml.safe_dump(raw))
    elif change == "config":
        path = configured.config_dir / "algorithms.yaml"
        raw = yaml.safe_load(path.read_text())
        raw["coverage_test_revision"] = 2
        path.write_text(yaml.safe_dump(raw))
    elif change == "validation":
        path = root / "validation/test-mars-source.json"
        raw = json.loads(path.read_text())
        raw["status"] = "FAIL"
        path.write_text(json.dumps(raw))
    elif change == "lock":
        path = root / "locks" / f"{POLICY}.json"
        raw = json.loads(path.read_text())
        raw["datasets"][0]["body"] = "MOON"
        path.write_text(json.dumps(raw))
    elif change == "missing-index":
        _index(configured).unlink()
    else:
        path = _index(configured)
        raw = json.loads(path.read_text())
        if change == "wrong-lock-index":
            raw["dataset_lock_id"] = "another-lock-v1"
            raw.pop("index_sha256")
            raw["index_sha256"] = canonical_sha256(raw)
        else:
            raw["datasets"][0]["bbox"] = [-180, -89, 180, 89]
        path.write_text(json.dumps(raw))
    response = _get(configured)
    assert response.state == "UNKNOWN" and response.basis == "UNAVAILABLE" and response.datasets == []
    assert str(root) not in response.model_dump_json() and "secret" not in response.model_dump_json()


@pytest.mark.parametrize(
    "bbox",
    [
        (3, 2, 1, 4),
        (1, 4, 3, 2),
        (1, 2, float("nan"), 4),
        (1, 2, float("inf"), 4),
        (-181, 2, 3, 4),
        (1, -90, 3, 4),
        (170, 2, -170, 4),
        (1, 2, 1, 4),
        (True, 2, 3, 4),
    ],
)
def test_invalid_boxes_rejected(configured, bbox):
    with pytest.raises(ApiError) as caught:
        _get(configured, bbox=bbox)
    assert caught.value.code == "INPUT_INVALID"


@pytest.mark.parametrize(
    "overrides",
    [{"body": "VENUS"}, {"body": "MOON"}, {"scenario_config_id": "missing"}, {"dataset_lock_id": "foreign-v1"}],
)
def test_body_scenario_and_lock_bindings_rejected(configured, overrides):
    with pytest.raises(ApiError) as caught:
        _get(configured, **overrides)
    assert caught.value.code == "INPUT_INVALID"


def test_earth_source_is_valid_for_mars_scenario_and_other_sources_not_leaked(configured):
    coverage.prepare_visualization_coverage(configured, POLICY)
    response = _get(configured, body="EARTH")
    assert response.state == "COVERED" and [row.id for row in response.datasets] == ["test-earth-source"]


@pytest.mark.parametrize("missing", ["index", "lock", "selector", "status", "locked-dataset", "null-lock"])
def test_unconfigured_is_unknown_even_when_global_assets_exist(configured, missing):
    if missing not in {"index", "lock"}:
        coverage.prepare_visualization_coverage(configured, POLICY)
    if missing == "lock":
        (configured.data_root / "locks" / f"{POLICY}.json").unlink()
    elif missing in {"selector", "status", "locked-dataset"}:
        path = configured.config_dir / "scenarios.yaml"
        raw = yaml.safe_load(path.read_text())
        if missing == "status":
            raw[SCENARIO]["status"] = "AWAITING_DATASETS"
        else:
            raw[SCENARIO]["target_source"] = (
                None if missing == "selector" else {"kind": "LOCAL_DATASET", "dataset_id": "not-in-this-lock"}
            )
        path.write_text(yaml.safe_dump(raw))
    response = _get(configured, **({"dataset_lock_id": None} if missing == "null-lock" else {}))
    assert response.state == "UNKNOWN" and response.datasets == []


def test_preparation_rejects_tampered_source_without_overwriting_index(configured):
    coverage.prepare_visualization_coverage(configured, POLICY)
    original = _index(configured).read_bytes()
    path = configured.data_root / "incoming/test-earth-source/terrain.tif"
    path.write_bytes(b"X" * path.stat().st_size)
    with pytest.raises(datasets.DatasetError, match="changed"):
        coverage.prepare_visualization_coverage(configured, POLICY)
    assert _index(configured).read_bytes() == original


@pytest.mark.parametrize("selector", ["test-earth-source", "absent-from-lock"])
def test_ineligible_selector_is_not_rescued_by_other_locked_data(configured, selector):
    path = configured.config_dir / "scenarios.yaml"
    raw = yaml.safe_load(path.read_text())
    raw[SCENARIO]["target_source"] = {"kind": "LOCAL_DATASET", "dataset_id": selector}
    path.write_text(yaml.safe_dump(raw))
    coverage.prepare_visualization_coverage(configured, POLICY)
    response = _get(configured)
    assert response.state == "UNKNOWN" and response.datasets == []


@pytest.mark.parametrize(
    "projection", ["+proj=utm +zone=12 +datum=WGS84 +type=crs", "+proj=longlat +datum=WGS84 +type=crs"]
)
def test_unsupported_projection_does_not_turn_outer_envelope_into_coverage(configured, projection):
    path = configured.data_root / "incoming/test-earth-source/manifest.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["crs"] = {"wkt": CRS.from_proj4(projection).to_wkt()}
    if "longlat" in projection:
        raw["longitude_direction"] = "POSITIVE_WEST"
    path.write_text(yaml.safe_dump(raw))
    manifest = datasets.load_manifest(configured, "test-earth-source")
    state = configured.data_root / "validation/test-earth-source.json"
    report = json.loads(state.read_text())
    report["manifest_sha256"] = canonical_sha256(manifest)
    state.write_text(json.dumps(report))
    (configured.data_root / "locks" / f"{POLICY}.json").unlink()
    datasets.create_lock(configured, POLICY, ["test-earth-source", "test-mars-source"])
    coverage.prepare_visualization_coverage(configured, POLICY)
    assert _get(configured, body="EARTH").state == "UNKNOWN"


def test_preparation_enforces_aggregate_byte_budget(configured):
    configured = configured.model_copy(update={"max_download_bytes": 1})
    with pytest.raises(datasets.DatasetError) as caught:
        coverage.prepare_visualization_coverage(configured, POLICY)
    assert caught.value.code == "RESOURCE_LIMIT"
    assert not _index(configured).exists()


def test_malformed_configuration_has_safe_unavailable_error(configured):
    (configured.config_dir / "scenarios.yaml").write_text("private-secret: [ malformed")
    with pytest.raises(ApiError) as caught:
        _get(configured)
    assert caught.value.status == 503
    assert "secret" not in caught.value.message


def test_index_byte_budget_fails_closed(configured):
    coverage.prepare_visualization_coverage(configured, POLICY)
    _index(configured).write_bytes(b" " * (coverage._MAX_JSON_BYTES + 1))
    assert _get(configured).state == "UNKNOWN"


def test_validated_spherical_mars_equidistant_cylindrical_is_supported(configured):
    path = configured.data_root / "incoming/test-mars-source/manifest.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["crs"] = {"wkt": CRS.from_proj4("+proj=eqc +R=3396190 +type=crs").to_wkt()}
    raw["longitude_convention"] = "PROJECTED"
    path.write_text(yaml.safe_dump(raw))
    manifest = datasets.load_manifest(configured, "test-mars-source")
    state = configured.data_root / "validation/test-mars-source.json"
    report = json.loads(state.read_text())
    report["manifest_sha256"] = canonical_sha256(manifest)
    state.write_text(json.dumps(report))
    (configured.data_root / "locks" / f"{POLICY}.json").unlink()
    datasets.create_lock(configured, POLICY, ["test-earth-source", "test-mars-source"])
    coverage.prepare_visualization_coverage(configured, POLICY)
    assert _get(configured).state == "COVERED"
