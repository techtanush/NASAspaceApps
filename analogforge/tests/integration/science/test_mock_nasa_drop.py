"""SCN-12 / MRG-05 rehearsal inputs: the nine datasets of architecture 39 section 5 - formats, quirks, determinism, and
(with the dataset ingest in place) the five good ones validate while each bad one fails exactly its named check."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml

from analogforge.ports.datasets import DatasetManifest
from analogforge.science.datasets.ingest import ingest_local_dataset
from analogforge.science.fixtures import mock_nasa_drop as drop
from analogforge.science.geometry import assert_crs_matches_body

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)


@pytest.fixture(scope="module")
def drop_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("mock-drop")
    assert drop.generate(out) == list(drop.ALL_IDS)
    return out


def manifest_of(root: Path, dataset_id: str) -> DatasetManifest:
    return DatasetManifest.model_validate(yaml.safe_load((root / dataset_id / "manifest.yaml").read_text("utf-8")))


def digest_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ----------------------------------------------------------------------------------------------- manifests / files
def test_nine_datasets_with_valid_synthetic_manifests(drop_dir: Path) -> None:
    assert sorted(p.name for p in drop_dir.iterdir()) == sorted(drop.ALL_IDS) and len(drop.ALL_IDS) == 9
    for dataset_id in drop.ALL_IDS:
        m = manifest_of(drop_dir, dataset_id)
        assert m.dataset_id == dataset_id
        assert m.provider == "SYNTHETIC_MOCK_NASA_DROP" and m.is_synthetic
        assert (m.product_identity.product_id or "").startswith("SYNTHETIC_")
        assert "not NASA data" in " ".join(m.notes)
        for f in m.files:
            data = (drop_dir / dataset_id / f.path).read_bytes()
            assert f.sha256 == hashlib.sha256(data).hexdigest(), (dataset_id, f.path)


def test_formats_cover_the_required_layouts(drop_dir: Path) -> None:
    formats = {d: manifest_of(drop_dir, d).format for d in drop.ALL_IDS}
    assert formats["mock-nasa-earth-dem"] == "HGT"
    assert formats["mock-nasa-lunar-radius"] == "PDS3_IMG"
    assert formats["mock-nasa-emit"] == "NETCDF"
    assert formats["mock-nasa-ascii-dem"] == "ASCII_GRID"
    assert formats["mock-nasa-mars-dem"] == "GEOTIFF"


def test_generation_is_byte_deterministic_and_seed_sensitive(tmp_path: Path) -> None:
    drop.generate(tmp_path / "a")
    drop.generate(tmp_path / "b")
    assert digest_tree(tmp_path / "a") == digest_tree(tmp_path / "b")
    drop.generate(tmp_path / "c", seed=7)
    assert digest_tree(tmp_path / "c") != digest_tree(tmp_path / "a")


def test_only_and_unknown_dataset(tmp_path: Path) -> None:
    assert drop.generate(tmp_path, only=["mock-nasa-ascii-dem"]) == ["mock-nasa-ascii-dem"]
    assert [p.name for p in tmp_path.iterdir()] == ["mock-nasa-ascii-dem"]
    with pytest.raises(KeyError):
        drop.generate(tmp_path, only=["nope"])


def test_hgt_tiles_share_the_seam_column_and_have_voids(drop_dir: Path) -> None:
    d = drop_dir / "mock-nasa-earth-dem"
    west = np.frombuffer((d / "N36W112.hgt").read_bytes(), dtype=">i2").reshape(1201, 1201)
    east = np.frombuffer((d / "N36W111.hgt").read_bytes(), dtype=">i2").reshape(1201, 1201)
    assert (d / "N36W112.hgt").stat().st_size == 1201 * 1201 * 2
    assert np.array_equal(west[:, 1200], east[:, 0])  # the border sample appears in both tiles
    assert (east == -32768).sum() == 400 and (west == -32768).sum() == 0
    assert int(west.max()) < 4000 and int(west[west != -32768].min()) > 0
    with rasterio.open(d / "N36W112.hgt") as src:
        assert src.driver == "SRTMHGT" and src.crs.to_epsg() == 4326 and src.shape == (1201, 1201)


def test_mars_dem_carries_gdal_scale_and_offset_once(drop_dir: Path) -> None:
    m = manifest_of(drop_dir, "mock-nasa-mars-dem")
    with rasterio.open(drop_dir / "mock-nasa-mars-dem" / m.primary_file) as src:
        assert src.scales == (m.scale_factor,) and src.offsets == (m.offset,)
        assert_crs_matches_body("MARS", src.crs.to_wkt())
        west = src.transform.c
    assert m.scale_already_applied and m.longitude_convention == "ZERO_360" and 180.0 < west < 360.0


def test_lunar_radius_pds3_label_and_scaling(drop_dir: Path) -> None:
    d = drop_dir / "mock-nasa-lunar-radius"
    label = (d / "ldem_mock.lbl").read_text("ascii")
    assert "SCALING_FACTOR" in label and "OFFSET" in label and "^IMAGE" in label
    m = manifest_of(drop_dir, "mock-nasa-lunar-radius")
    assert m.quantity == "RADIUS" and m.units == "km" and m.reference_radius_m == 1737400.0
    with rasterio.open(d / "ldem_mock.lbl") as src:
        assert src.driver == "PDS" and src.scales == (m.scale_factor,) and src.offsets == (m.offset,)
        radius_km = src.read(1).astype(float) * m.scale_factor + m.offset
        assert_crs_matches_body("MOON", src.crs.to_wkt())
    assert 1737.4 < radius_km.min() and radius_km.max() < 1745.0


def test_emit_netcdf_group_variable_and_fill(drop_dir: Path) -> None:
    m = manifest_of(drop_dir, "mock-nasa-emit")
    assert m.variable == "mineral_metadata/group_1_mineral_id"
    path = drop_dir / "mock-nasa-emit" / m.primary_file
    with rasterio.open(f'NETCDF:"{path}":{m.variable}') as src:
        ids = src.read(1)
        assert src.nodata == -9999.0 and src.crs.to_epsg() == 4326
    assert set(np.unique(ids[ids != -9999])) <= {1, 2, 3, 4} and (ids == -9999).any()


def test_ascii_grid_header_prj_and_nodata(drop_dir: Path) -> None:
    d = drop_dir / "mock-nasa-ascii-dem"
    head = (d / "ascii_dem.asc").read_text("ascii").splitlines()[:6]
    assert head[0].startswith("ncols") and any(h.startswith("NODATA_value") for h in head)
    assert (d / "ascii_dem.prj").read_text("ascii").startswith("PROJCS")
    with rasterio.open(d / "ascii_dem.asc") as src:
        assert src.crs.to_epsg() == 32612 and src.nodata == -9999.0


def test_bad_datasets_carry_their_defect(drop_dir: Path) -> None:
    html = (drop_dir / "mock-nasa-bad-html" / "login.tif").read_bytes()
    assert html.lstrip().lower().startswith((b"<!doctype", b"<html"))
    with rasterio.open(drop_dir / "mock-nasa-bad-no-crs" / "no_crs.tif") as src:
        assert src.crs is None
    m = manifest_of(drop_dir, "mock-nasa-bad-double-scale")
    with rasterio.open(drop_dir / m.dataset_id / m.primary_file) as src:
        assert src.scales == (m.scale_factor,) and src.offsets == (m.offset,)  # both file and manifest carry it
    assert m.scale_factor != 1.0 and not m.scale_already_applied
    m = manifest_of(drop_dir, "mock-nasa-bad-units")
    with rasterio.open(drop_dir / m.dataset_id / m.primary_file) as src:
        assert float(src.read(1).min()) > 1.0e6  # radii in metres
    assert m.quantity == "ELEVATION" and m.body == "MOON"


# ----------------------------------------------------------------------------------------------- ingest (SCN-12)
def ingest(root: Path, dataset_id: str, scratch: Path):  # type: ignore[no-untyped-def]
    manifest = yaml.safe_load((root / dataset_id / "manifest.yaml").read_text("utf-8"))
    return ingest_local_dataset(root / dataset_id, manifest, scratch)


@pytest.mark.parametrize("dataset_id", drop.GOOD_IDS)
def test_good_datasets_validate(drop_dir: Path, tmp_path: Path, dataset_id: str) -> None:
    result = ingest(drop_dir, dataset_id, tmp_path)
    assert result.failed == ()
    assert result.usable_for_quantitative_claims


@pytest.mark.parametrize(("dataset_id", "check_id"), sorted(drop.BAD_EXPECTED_CHECK.items()))
def test_bad_datasets_fail_exactly_the_named_check(
    drop_dir: Path, tmp_path: Path, dataset_id: str, check_id: str
) -> None:
    result = ingest(drop_dir, dataset_id, tmp_path)
    assert result.failed == (check_id,)
    assert not result.usable_for_quantitative_claims


def test_one_flipped_byte_is_a_checksum_failure(drop_dir: Path, tmp_path: Path) -> None:
    import shutil

    copy = tmp_path / "copy"
    shutil.copytree(drop_dir / "mock-nasa-earth-dem", copy / "mock-nasa-earth-dem")
    tile = copy / "mock-nasa-earth-dem" / "N36W112.hgt"
    data = bytearray(tile.read_bytes())
    data[5000] ^= 0x01
    tile.write_bytes(bytes(data))
    result = ingest(copy, "mock-nasa-earth-dem", tmp_path / "scratch")
    assert "checksums" in result.failed
