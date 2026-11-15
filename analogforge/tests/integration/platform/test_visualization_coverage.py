"""Real frozen-facade intake produces footprint metadata; HTTP reads do no science."""

from __future__ import annotations

import json
import shutil

import numpy as np
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin

from analogforge.application import datasets
from analogforge.application import visualization_coverage as coverage
from analogforge.ports.hashing import file_sha256
from analogforge.settings import Settings


def test_real_intake_preparation_then_metadata_only_coverage(tmp_path, monkeypatch):
    config = tmp_path / "config"
    shutil.copytree(Settings(_env_file=None).config_dir, config)
    settings = Settings(_env_file=None, data_root=tmp_path / "data", config_dir=config)
    dataset_id, policy = "coverage-geographic-fixture", "coverage-real-intake-v1"
    root = settings.data_root / "incoming" / dataset_id
    root.mkdir(parents=True)
    source = root / "terrain.tif"
    values = np.arange(32 * 32, dtype=np.int16).reshape(32, 32)
    values[0, 0] = -32768
    west, north, step = -111.58, 35.31, 1 / 3600
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        width=32,
        height=32,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=from_origin(west, north, step, step),
        nodata=-32768,
    ) as raster:
        raster.write(values, 1)
    manifest = {
        "dataset_id": dataset_id,
        "title": "Synthetic coverage intake fixture",
        "provider": "SYNTHETIC_TEST",
        "is_synthetic": True,
        "body": "EARTH",
        "role": "EARTH_TERRAIN",
        "format": "GEOTIFF",
        "files": [{"path": "terrain.tif", "sha256": file_sha256(source)}],
        "primary_file": "terrain.tif",
        "quantity": "ELEVATION",
        "units": "m",
        "nodata_value": -32768,
        "vertical_reference": "SYNTHETIC_TEST_REFERENCE",
        "crs": {"epsg": 4326},
        "longitude_convention": "NEG180_180",
        "latitude_type": "GEODETIC",
        "pixel_registration": "CORNER",
        "license_note": "Synthetic unit fixture, no NASA measurement",
        "citation": "Generated in test",
        "product_identity": {"product_id": "synthetic-coverage", "version": "test-v1"},
    }
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    report = datasets.validate_dataset(settings, dataset_id)
    assert report["status"] == "PASS" and report["usable_for_quantitative_claims"] is True
    assert len(report["checks"]) == 15
    datasets.create_lock(settings, policy, [dataset_id])
    path = config / "scenarios.yaml"
    scenarios = yaml.safe_load(path.read_text())
    scenario_id = "local-dataset-practice-v1"
    scenarios[scenario_id].update(
        status="AVAILABLE",
        default_dataset_lock_id=policy,
        target_source=None,
        earth_source={"kind": "LOCAL_DATASET", "dataset_id": dataset_id},
        additional_sources={},
    )
    path.write_text(yaml.safe_dump(scenarios))
    original_sources = {path: path.read_bytes() for path in settings.data_root.rglob("*") if path.is_file()}
    prepared = coverage.prepare_visualization_coverage(settings, policy)
    assert prepared["footprints"] == 1
    assert all(path.read_bytes() == content for path, content in original_sources.items())
    index = json.loads((settings.data_root / "visualization/coverage" / f"{policy}.json").read_text())
    assert index["datasets"][0]["bbox"] == pytest.approx([west, north - 32 * step, west + 32 * step, north])

    def forbidden(*args, **kwargs):
        pytest.fail("HTTP may not execute a facade, download data or open a raster")

    monkeypatch.setattr(coverage, "_entrypoint", forbidden)
    monkeypatch.setattr(rasterio, "open", forbidden)
    monkeypatch.setattr(datasets, "file_sha256", forbidden)
    response = coverage.get_visualization_coverage(
        settings,
        body="EARTH",
        bbox=(west + step, north - 31 * step, west + 31 * step, north - step),
        scenario_config_id=scenario_id,
        dataset_lock_id=policy,
    )
    assert response.state == "COVERED" and response.basis == "VALIDATED_FOOTPRINT"
    assert response.datasets[0].native_resolution_m is not None
    assert 25 < response.datasets[0].native_resolution_m < 32
    assert response.datasets[0].comparison_support_m is None
    assert "valid-cell" in response.reason  # A real nodata cell is not mislabeled mask-level coverage.
