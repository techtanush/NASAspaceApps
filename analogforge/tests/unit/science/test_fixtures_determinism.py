"""Fixture generators: byte determinism, seed/parameter sensitivity, SYNTHETIC naming, in-memory loader parity with
the file path (PARITY-01 precondition) and failure paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml

from analogforge.ports import catalog
from analogforge.ports.datasets import DatasetManifest
from analogforge.science.fixtures import graph, practice
from analogforge.science.fixtures.practice import PracticeOptions, make_options
from analogforge.science.raster.normalize import normalize_elevation
from analogforge.science.raster.source import read_gdal_raster


def tree_digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("practice-det")
    practice.generate_all(out)
    return out


def test_generate_all_returns_every_dataset_of_arch_40(tmp_path: Path) -> None:
    ids = practice.generate_all(tmp_path)
    assert set(ids) == {
        catalog.FIXTURE_MARS_TARGET,
        catalog.FIXTURE_MOON_TARGET,
        catalog.FIXTURE_EARTH_GRID,
        "practice-moon-thermal-v1",
        "practice-earth-minerals-v1",
    }
    assert (tmp_path / "practice-earth-grid-v1" / "practice-earth-grid-v1-water.tif").is_file()
    for dataset_id in ids:
        assert (tmp_path / dataset_id / "manifest.yaml").is_file()


def test_two_runs_are_byte_identical(generated: Path, tmp_path: Path) -> None:
    practice.generate_all(tmp_path)
    assert tree_digest(generated) == tree_digest(tmp_path)


def test_seed_and_parameters_change_the_right_bytes(generated: Path, tmp_path: Path) -> None:
    base = tree_digest(generated)
    practice.generate_all(tmp_path / "seed", seed=99)
    seeded = tree_digest(tmp_path / "seed")
    for name in (
        "practice-earth-grid-v1/practice-earth-grid-v1.tif",
        "practice-moon-thermal-v1/practice-moon-thermal-v1.tif",
    ):
        assert seeded[name] != base[name], name
    # seed-free geometry (strips, rings, water mask) is unchanged by the seed
    for name in (
        "practice-mars-target-v1/practice-mars-target-v1.tif",
        "practice-moon-target-v1/practice-moon-target-v1.tif",
        "practice-earth-grid-v1/practice-earth-grid-v1-water.tif",
    ):
        assert seeded[name] == base[name], name
    practice.generate_all(tmp_path / "moat", moat_cells=0)
    changed = {k for k, v in tree_digest(tmp_path / "moat").items() if base[k] != v}
    assert any(k.startswith("practice-earth-grid-v1/") for k in changed)
    assert not any(k.startswith(("practice-mars", "practice-moon", "practice-earth-minerals")) for k in changed)


def test_manifests_validate_and_are_synthetic(generated: Path) -> None:
    for d in sorted(generated.iterdir()):
        m = DatasetManifest.model_validate(yaml.safe_load((d / "manifest.yaml").read_text("utf-8")))
        assert m.dataset_id == d.name and m.is_synthetic and m.provider == "SYNTHETIC_PRACTICE"
        assert (m.product_identity.product_id or "").startswith("SYNTHETIC_")
        assert (
            "NASADEM" not in m.model_dump_json()
            and "MOLA" not in m.model_dump_json()
            and "LOLA" not in m.model_dump_json()
        )
        for f in m.files:
            assert f.sha256 == hashlib.sha256((d / f.path).read_bytes()).hexdigest()


def test_moon_target_uses_scale_offset_once_and_no_file_scale_tags(generated: Path) -> None:
    m = DatasetManifest.model_validate(
        yaml.safe_load((generated / "practice-moon-target-v1" / "manifest.yaml").read_text())
    )
    assert (m.scale_factor, m.offset, m.scale_already_applied, m.quantity, m.reference_radius_m) == (
        0.5,
        1737400.0,
        False,
        "RADIUS",
        1737400.0,
    )
    with rasterio.open(generated / m.dataset_id / m.primary_file) as src:
        assert src.dtypes[0] == "int16" and src.scales == (1.0,) and src.offsets == (0.0,)


@pytest.mark.parametrize("fixture_id", graph.RASTER_FIXTURE_IDS)
def test_in_memory_fixture_equals_the_file_read_through_the_dataset_path(fixture_id: str, generated: Path) -> None:
    """SYNTHETIC_FIXTURE and LOCAL_DATASET give identical rasters: same raw bytes, same normalisation."""
    arrays = graph.load_fixture_arrays(fixture_id)
    m = arrays.manifest
    raw = read_gdal_raster(generated / fixture_id / m.primary_file)
    if m.quantity in ("ELEVATION", "RADIUS"):
        assert m.units in ("m", "km")
        values, missing, _ = normalize_elevation(
            raw.values,
            quantity=m.quantity,
            units=m.units,
            scale_factor=m.scale_factor,
            offset=m.offset,
            scale_already_applied=m.scale_already_applied,
            reference_radius_m=m.reference_radius_m,
            nodata_value=raw.nodata_value,
        )
    else:
        missing = raw.values == raw.nodata_value
        values = np.where(missing, np.nan, raw.values.astype(np.float64))
    assert np.array_equal(arrays.missing, missing)
    assert np.array_equal(arrays.values[~missing], values[~missing])
    assert arrays.grid.shape == raw.values.shape
    assert arrays.grid.origin_x_m == raw.geotransform[0] and arrays.grid.origin_y_m == raw.geotransform[3]
    assert arrays.product_id.startswith("SYNTHETIC_")


def test_source_raster_is_synthetic_with_water_mask_and_nan_nodata() -> None:
    src = graph.load_source_raster(catalog.FIXTURE_EARTH_GRID)
    assert src.synthetic and (src.product_id or "").startswith("SYNTHETIC_") and src.body == "EARTH"
    assert src.water is not None and src.water.sum() > 4000
    assert np.isnan(src.values[src.nodata]).all() and src.nodata.any()
    assert src.native_resolution_m == 60.0 and src.grid.shape == (192, 192)
    moon = graph.load_source_raster(catalog.FIXTURE_MOON_TARGET)
    assert moon.body == "MOON" and moon.native_resolution_m == 960.0 and abs(float(np.nanmedian(moon.values))) < 20000.0
    assert not np.isnan(moon.values).any()  # radius converted to height exactly once (no 1.7e6 magnitudes left)


def test_perturbed_options_flow_into_the_in_memory_loader() -> None:
    base = graph.load_source_raster(catalog.FIXTURE_EARTH_GRID)
    moved = graph.load_source_raster(catalog.FIXTURE_EARTH_GRID, make_options(moat_cells=0))
    assert base.water is not None and moved.water is not None
    assert int(base.water.sum()) > int(moved.water.sum())


def test_canonical_graph_loader_matches_the_catalog() -> None:
    spec = graph.load_canonical_graph()
    assert set(spec.nodes) == {"S", "A", "B", "C", "W1", "W2"} and len(spec.edges) == 6
    assert len(graph.load_canonical_graph(drop_edges=(("S", "B"),)).edges) == 5


def test_failure_paths(tmp_path: Path) -> None:
    with pytest.raises(graph.UnknownFixtureError):
        graph.load_fixture_arrays("practice-unknown-v9")
    with pytest.raises(graph.UnknownFixtureError):
        graph.load_source_raster("practice-earth-minerals-v1")  # categorical, not terrain
    with pytest.raises(KeyError):
        practice.generate_all(tmp_path, only=["nope"])
    with pytest.raises(KeyError):
        practice.build_product("nope", PracticeOptions())
