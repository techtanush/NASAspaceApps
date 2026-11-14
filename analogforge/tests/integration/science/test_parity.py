"""SCN-13 (PARITY-01): a raster reached through the fixture path (in-memory ``build_product``) and the same raster
reached through the dataset slot (files + ``manifest.yaml`` -> ``INGEST_LOCAL_DATASET``) give identical values and
identical derived metrics.  Also: the practice datasets themselves validate through the real slot."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from analogforge.science.datasets.ingest import IngestResult, ingest_local_dataset
from analogforge.science.datasets.registry import load_manifest_file
from analogforge.science.features.histogram import SLOPE_HIST_EDGES, area_weighted_histogram
from analogforge.science.features.slope import analyze_surface
from analogforge.science.fixtures.practice import ALL_DATASET_IDS, build_product, generate_all
from analogforge.science.geometry import PixelGeometry

ELEVATION_IDS = [d for d in ALL_DATASET_IDS if "target" in d or "earth-grid" in d]


@pytest.fixture(scope="module")
def incoming(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("incoming")
    generate_all(root)
    return root


def ingest_from_files(incoming: Path, dataset_id: str, scratch: Path) -> IngestResult:
    d = incoming / dataset_id
    return ingest_local_dataset(d, load_manifest_file(d), scratch)


@pytest.mark.parametrize("dataset_id", ALL_DATASET_IDS)
def test_practice_datasets_validate_through_the_slot(incoming: Path, tmp_path: Path, dataset_id: str) -> None:
    r = ingest_from_files(incoming, dataset_id, tmp_path)
    assert r.failed == (), [(c.check_id, c.message) for c in r.checks if c.status == "FAIL"]
    assert r.usable_for_quantitative_claims, [(c.check_id, c.status, c.message) for c in r.checks if c.status != "PASS"]
    assert r.product_id is not None and r.product_id.startswith("SYNTHETIC_")
    assert r.manifest is not None and r.manifest.is_synthetic and r.manifest.provider.startswith("SYNTHETIC")


@pytest.mark.parametrize("dataset_id", ELEVATION_IDS)
def test_values_identical_between_fixture_and_local_dataset_paths(
    incoming: Path, tmp_path: Path, dataset_id: str
) -> None:
    product = build_product(dataset_id)
    m = product.manifest
    r = ingest_from_files(incoming, dataset_id, tmp_path)
    assert r.raster is not None
    primary = product.primary
    raw = primary.array.astype(np.float64)
    missing = ~np.isfinite(raw)
    if primary.nodata is not None:
        missing |= raw == primary.nodata
    expected = np.where(missing, np.nan, raw * m.scale_factor + m.offset)
    if m.quantity == "RADIUS":
        expected = expected * (1000.0 if m.units == "km" else 1.0) - float(m.reference_radius_m or 0.0)
    elif m.units == "km":
        expected = expected * 1000.0
    assert r.raster.values.shape == expected.shape
    assert np.array_equal(r.raster.values, expected, equal_nan=True)
    gt = r.raster.geotransform
    assert (gt[0], gt[3]) == (primary.origin_x_m, primary.origin_y_m)
    assert gt[1] == primary.cell_size_m and gt[5] == -primary.cell_size_m


@pytest.mark.parametrize("dataset_id", ELEVATION_IDS)
def test_derived_metrics_identical_between_paths(incoming: Path, tmp_path: Path, dataset_id: str) -> None:
    product = build_product(dataset_id)
    r = ingest_from_files(incoming, dataset_id, tmp_path)
    assert r.raster is not None
    cell = product.primary.cell_size_m
    geom = PixelGeometry.north_up(cell)
    direct = np.where(
        np.isfinite(product.primary.array) & (product.primary.array != (product.primary.nodata or np.inf)),
        product.primary.array.astype(np.float64) * product.manifest.scale_factor + product.manifest.offset,
        np.nan,
    )
    if product.manifest.quantity == "RADIUS":
        direct = direct * (1000.0 if product.manifest.units == "km" else 1.0) - float(
            product.manifest.reference_radius_m or 0
        )
    a = analyze_surface(direct, geom)
    b = analyze_surface(r.raster.values, geom)
    assert np.array_equal(a.valid, b.valid)
    assert np.array_equal(a.slope_deg, b.slope_deg, equal_nan=True)
    ha = area_weighted_histogram(a.slope_deg, a.valid & a.land, cell * cell, SLOPE_HIST_EDGES)
    hb = area_weighted_histogram(b.slope_deg, b.valid & b.land, cell * cell, SLOPE_HIST_EDGES)
    assert np.array_equal(ha.area_m2, hb.area_m2)
    assert float(ha.valid_area_m2) > 0.0
    assert r.payload is not None and r.payload.valid_fraction == pytest.approx(float(np.mean(np.isfinite(direct))))


def test_parity_is_sensitive_to_a_perturbed_dataset(tmp_path: Path) -> None:
    """Perturbation: change the generator parameters and the ingested metrics change (not constants)."""
    base, other = tmp_path / "base", tmp_path / "other"
    generate_all(base, only=[ELEVATION_IDS[0]])
    generate_all(other, only=[ELEVATION_IDS[0]], target_fractions=((5.0, 0.9), (30.0, 0.1)), ramp_slope_deg=17.0)
    rb = ingest_from_files(base, ELEVATION_IDS[0], tmp_path / "s1")
    ro = ingest_from_files(other, ELEVATION_IDS[0], tmp_path / "s2")
    assert rb.raster is not None and ro.raster is not None
    assert rb.raster.values_sha256 != ro.raster.values_sha256


def test_practice_slot_is_synthetic_never_labelled_nasa(incoming: Path, tmp_path: Path) -> None:
    for dataset_id in ALL_DATASET_IDS:
        r = ingest_from_files(incoming, dataset_id, tmp_path)
        assert r.manifest is not None
        text = (r.manifest.provider + (r.product_id or "")).upper()
        assert "NASADEM" not in text and "MOLA" not in text and "LOLA" not in text


MOCK_BAD = {
    "mock-nasa-bad-no-crs": "crs_resolved",
    "mock-nasa-bad-html": "html_login_page",
    "mock-nasa-bad-double-scale": "scale_offset_once",
    "mock-nasa-bad-units": "units_and_quantity",
}
MOCK_GOOD = (
    "mock-nasa-earth-dem",
    "mock-nasa-mars-dem",
    "mock-nasa-lunar-radius",
    "mock-nasa-emit",
    "mock-nasa-ascii-dem",
)


def test_mock_nasa_drop_good_datasets_validate_and_bad_ones_fail_exactly(tmp_path: Path) -> None:
    from analogforge.science.fixtures import mock_nasa_drop

    root = tmp_path / "incoming"
    mock_nasa_drop.generate(root)
    for dataset_id in MOCK_GOOD:
        r = ingest_from_files(root, dataset_id, tmp_path / "s")
        assert r.failed == () and r.usable_for_quantitative_claims, dataset_id
    for dataset_id, check_id in MOCK_BAD.items():
        r = ingest_from_files(root, dataset_id, tmp_path / "s")
        assert r.failed == (check_id,), (dataset_id, r.failed)
        assert not r.usable_for_quantitative_claims
