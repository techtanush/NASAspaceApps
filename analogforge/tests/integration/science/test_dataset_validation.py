"""SCN-11 / SCN-14: INGEST_LOCAL_DATASET runs every check of architecture 36 section 4, one failing fixture per
``check_id``, a passing fixture per good format, ``usable_for_quantitative_claims`` rules, archive safety, purity,
scaffolding (``draft_manifest``), registry/locks and Moon polar / longitude-wrap behaviour."""

from __future__ import annotations

import copy
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
import yaml
from rasterio.transform import Affine, from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fixtures" / "science" / "datasets"))
import dataset_builders as b  # noqa: E402

from analogforge.ports.hashing import file_sha256  # noqa: E402
from analogforge.science.datasets import checks as ck  # noqa: E402
from analogforge.science.datasets.ingest import (  # noqa: E402
    DatasetUnreadableError,
    IngestResult,
    ingest_local_dataset,
    source_evidence_draft,
)
from analogforge.science.datasets.inspect import draft_manifest, dump_draft_yaml  # noqa: E402
from analogforge.science.datasets.registry import (  # noqa: E402
    DatasetRegistry,
    RegistryError,
    assert_scratch_write_allowed,
    build_lock,
    has_unfilled_fields,
    list_dataset_ids,
    load_manifest_file,
    lock_entry,
    lock_is_consistent,
    lock_to_bytes,
    resolve_dataset_dir,
    validate_dataset_id,
    verify_lock_integrity,
)
from analogforge.science.errors import ScienceError  # noqa: E402

Manifest = dict[str, Any]


def run(root: Path, manifest: Manifest, **kw: Any) -> IngestResult:
    return ingest_local_dataset(root / manifest["dataset_id"], manifest, root / "scratch", **kw)


def status(result: IngestResult) -> dict[str, str]:
    return {c.check_id: c.status for c in result.checks}


def build(root: Path, kind: str) -> Manifest:
    return b.GOOD_BUILDERS[kind](root)


def only_fails(result: IngestResult, *expected: str) -> None:
    assert set(result.failed) == set(expected), [
        (c.check_id, c.status, c.message) for c in result.checks if c.status != "PASS"
    ]


# ------------------------------------------------------------------------------------------------ passing fixtures
@pytest.mark.parametrize("kind", sorted(b.GOOD_BUILDERS))
def test_good_format_passes_all_fifteen_checks_in_order(tmp_path: Path, kind: str) -> None:
    manifest = build(tmp_path, kind)
    result = run(tmp_path, manifest)
    assert [c.check_id for c in result.checks] == list(ck.CHECK_IDS)
    assert len(ck.CHECK_IDS) == 15
    assert result.failed == (), [(c.check_id, c.message) for c in result.checks if c.status != "PASS"]
    assert not [c for c in result.checks if c.status == "WARN" and c.check_id != "transform_sane"]
    assert result.usable_for_quantitative_claims is True
    p = result.payload
    assert p is not None and p.usable_for_quantitative_claims
    assert p.normalized_evidence is not None and p.normalized_evidence.local_key == f"source-{manifest['dataset_id']}"
    assert p.native_resolution_m is not None and p.native_resolution_m > 0
    assert p.valid_fraction is not None and 0.9 <= p.valid_fraction <= 1.0
    assert p.bbox_lonlat is not None
    assert result.raster is not None and np.isfinite(result.raster.values[~result.raster.missing]).all()
    assert np.isnan(result.raster.values[result.raster.missing]).all()  # unknown is NaN, never 0


def test_geotiff_values_and_nodata_are_exact(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    r = run(tmp_path, manifest)
    expected = b.ramp(20, 20).astype("float32").astype(np.float64)
    assert r.raster is not None
    got = r.raster.values
    assert np.isnan(got[2, 3]) and np.isnan(got[10, 10]) and int(np.isnan(got).sum()) == 2
    keep = ~np.isnan(got)
    assert np.array_equal(got[keep], expected[keep])
    assert r.payload is not None and r.payload.valid_fraction == pytest.approx(398 / 400)
    assert r.applied is not None and r.applied.scale_applied_by == "NONE"


def test_scale_offset_applied_exactly_once_on_reader_side(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_mars_scaled")
    r = run(tmp_path, manifest)
    raw = (np.arange(24 * 24).reshape(24, 24) % 400 + 200).astype(np.float64)
    expected = raw * 0.5 - 100.0
    assert r.raster is not None and r.applied is not None
    assert r.applied.scale_applied_by == "READER" and (r.applied.scale_factor, r.applied.offset) == (0.5, -100.0)
    assert np.isnan(r.raster.values[0, 0])
    assert np.array_equal(r.raster.values[1:, :], expected[1:, :])  # scaled once, not twice
    assert r.scale_decision is not None and not r.scale_decision.ambiguous


def test_manifest_scale_applied_on_analysis_side_when_file_has_none(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest.update(scale_factor=2.0, offset=5.0)
    r = run(tmp_path, manifest)
    assert status(r)["scale_offset_once"] == "PASS"
    assert r.applied is not None and r.applied.scale_applied_by == "ANALYSIS"
    expected = b.ramp(20, 20).astype("float32").astype(np.float64) * 2.0 + 5.0
    assert r.raster is not None and r.raster.values[0, 0] == expected[0, 0]


def test_radius_to_height_subtracted_exactly_once(tmp_path: Path) -> None:
    manifest = build(tmp_path, "pds3_radius")
    r = run(tmp_path, manifest)
    assert r.raster is not None and r.applied is not None
    assert (
        r.applied.radius_subtracted and r.applied.reference_radius_m == 1737400 and r.applied.unit_factor_to_m == 1000.0
    )
    vals = r.raster.values.ravel()
    assert np.isnan(vals[5])
    idx = np.array([i for i in range(400) if i != 5])
    assert np.allclose(vals[idx], idx.astype(float), atol=1e-6)  # height_m == raw (0..399 m): no double subtraction
    assert r.raster.vertical_reference.startswith("Lunar reference sphere")


def test_pds4_scale_offset_and_moon_equirectangular(tmp_path: Path) -> None:
    manifest = build(tmp_path, "pds4")
    r = run(tmp_path, manifest)
    assert r.raster is not None and r.raster.source_driver == "PDS4"
    flat = r.raster.values.ravel()
    assert np.isnan(flat[3])
    assert np.allclose(np.delete(flat, 3), np.delete(np.arange(24) * 0.5 + 10.0, 3))
    assert r.payload is not None and r.payload.native_resolution_m == pytest.approx(1000.0, rel=1e-6)


def test_hgt_tiles_mosaic_with_shared_border_sample_once(tmp_path: Path) -> None:
    manifest = build(tmp_path, "hgt_pair")
    r = run(tmp_path, manifest)
    assert r.raster is not None
    assert r.raster.values.shape == (1201, 2401)  # 1201 + 1201 - 1 shared column
    col = r.raster.values[:, 1200]
    rows = np.arange(1201)
    lon, lat = -111.0, 36 + 1 - rows / 1200.0
    expected = np.floor(1000 + 300 * np.sin(lon * 7.0) + 200 * np.cos(lat * 5.0))
    assert np.array_equal(col, expected)
    assert np.isnan(r.raster.values[100:104, 100:104]).all()  # void -32768 -> missing, not -32768
    assert r.raster.values[~np.isnan(r.raster.values)].min() > -1000


def test_hgt_zip_extracts_only_into_scratch(tmp_path: Path) -> None:
    manifest = build(tmp_path, "hgt_zip")
    before = sorted(p.name for p in (tmp_path / manifest["dataset_id"]).iterdir())
    r = run(tmp_path, manifest)
    assert r.failed == ()
    assert sorted(p.name for p in (tmp_path / manifest["dataset_id"]).iterdir()) == before
    assert any(p.suffix == ".hgt" for p in (tmp_path / "scratch").rglob("*"))


def test_netcdf_group_variable_keeps_categorical_ids(tmp_path: Path) -> None:
    manifest = build(tmp_path, "netcdf_emit")
    r = run(tmp_path, manifest)
    assert r.raster is not None
    ids = (np.arange(30).reshape(5, 6) % 4).astype(float)
    ids[0, 0] = np.nan
    assert np.array_equal(r.raster.values, ids, equal_nan=True)  # ids exact: no interpolation/rounding


def test_ascii_grid_nodata_and_projected_crs(tmp_path: Path) -> None:
    manifest = build(tmp_path, "ascii_grid")
    r = run(tmp_path, manifest)
    assert r.raster is not None and r.raster.source_driver == "AAIGrid"
    assert np.isnan(r.raster.values[1, 1]) and int(np.isnan(r.raster.values).sum()) == 1
    assert r.raster.values[0, 0] == pytest.approx(b.ramp(5, 6).round(1)[0, 0])


# ------------------------------------------------------------------------------------------------ failing fixtures
def _set(**kw: Any) -> Callable[[Path, Manifest], None]:
    def edit(_d: Path, m: Manifest) -> None:
        m.update(kw)

    return edit


def _drop(key: str) -> Callable[[Path, Manifest], None]:
    def edit(_d: Path, m: Manifest) -> None:
        del m[key]

    return edit


def _rewrite_tif(d: Path, name: str, **kw: Any) -> None:
    """Rewrite the (float32) GeoTIFF ``name`` with changed profile/data options."""
    with rasterio.open(d / name) as src:
        data = src.read(1)
        prof = src.profile
        scales, offsets = src.scales, src.offsets
    data = kw.pop("data", data)
    prof.update(kw)
    with rasterio.open(d / name, "w", **prof) as dst:
        dst.write(data, 1)
        dst.scales, dst.offsets = scales, offsets


def _no_crs(d: Path, m: Manifest) -> None:
    _rewrite_tif(d, "dem.tif", crs=None)


def _south_up(d: Path, m: Manifest) -> None:
    _rewrite_tif(d, "dem.tif", transform=Affine(30, 0, 500000, 0, 30, 4000000))


def _rotated(d: Path, m: Manifest) -> None:
    _rewrite_tif(d, "dem.tif", transform=Affine(30, 5, 500000, 5, -30, 4000000))


def _sentinel_without_nodata(d: Path, m: Manifest) -> None:
    data = b.ramp(20, 20).astype("float32")
    data[4, 4] = -9999
    _rewrite_tif(d, "dem.tif", data=data, nodata=None)
    m["nodata_value"] = None


def _zero_border(d: Path, m: Manifest) -> None:
    data = b.ramp(20, 20).astype("float32")
    data[0, :] = 0
    _rewrite_tif(d, "dem.tif", data=data, nodata=None)
    m["nodata_value"] = None


def _all_nodata(d: Path, m: Manifest) -> None:
    _rewrite_tif(d, "dem.tif", data=np.full((20, 20), -32768, dtype="float32"))


def _mostly_nodata(d: Path, m: Manifest) -> None:
    data = b.ramp(20, 20).astype("float32")
    data[:, 6:] = -32768  # 30 % valid
    _rewrite_tif(d, "dem.tif", data=data)


def _radius_as_elevation(d: Path, m: Manifest) -> None:
    data = (1737400.0 + b.ramp(20, 20)).astype("float32")
    _rewrite_tif(d, "dem.tif", data=data)


def _html_as_tif(d: Path, m: Manifest) -> None:
    (d / "dem.tif").write_bytes(b.html_login_page())


def _garbage_tif(d: Path, m: Manifest) -> None:
    (d / "dem.tif").write_bytes(b"\x00\x01not a raster at all" * 20)


def _delete_data(d: Path, m: Manifest) -> None:
    (d / "dem.tif").unlink()


def _symlink_escape(d: Path, m: Manifest) -> None:
    outside = d.parent / "outside.tif"
    outside.write_bytes((d / "dem.tif").read_bytes())
    (d / "dem.tif").unlink()
    (d / "dem.tif").symlink_to(outside)


def _bad_sha(d: Path, m: Manifest) -> None:
    m["files"][0]["sha256"] = "0" * 64


def _planetary_wkt_wrong_radius(d: Path, m: Manifest) -> None:
    m["crs"] = {"wkt": b.MOON_GEO_WKT}  # a Moon sphere on a Mars dataset (planet vs planet: body_consistent only)
    # the file CRS is also rewritten, so the two CRS agree and crs_resolved passes
    _rewrite_tif(d, "mola.tif", crs=rasterio.crs.CRS.from_wkt(b.MOON_GEO_WKT))


def _earth_crs_on_mars(d: Path, m: Manifest) -> None:
    m["crs"] = {"wkt": rasterio.crs.CRS.from_epsg(4326).to_wkt()}


def _double_scale(d: Path, m: Manifest) -> None:
    m.update(scale_factor=0.5, offset=-100.0, scale_already_applied=False)  # file ALSO carries 0.5/-100


def _file_scale_not_declared(d: Path, m: Manifest) -> None:
    m.update(scale_factor=1.0, offset=0.0, scale_already_applied=False)


def _claims_reader_scale_but_none(d: Path, m: Manifest) -> None:
    m.update(scale_factor=3.0, offset=0.0, scale_already_applied=True)


def _wrong_resolution(d: Path, m: Manifest) -> None:
    m["declared_native_resolution_m"] = 100  # actual 30 m


def _slight_resolution_error(d: Path, m: Manifest) -> None:
    m["declared_native_resolution_m"] = 30 * 1.08


def _hgt_zero_360(d: Path, m: Manifest) -> None:
    m["longitude_convention"] = "ZERO_360"  # tiles are at -112..-110


def _projected_on_geographic(d: Path, m: Manifest) -> None:
    m["longitude_convention"] = "PROJECTED"


def _mars_neg180(d: Path, m: Manifest) -> None:
    m["longitude_convention"] = "NEG180_180"  # raster is 180..186 east of Greenwich


def _blank_license(d: Path, m: Manifest) -> None:
    m["license_note"] = "   "


def _signed_url(d: Path, m: Manifest) -> None:
    m["product_identity"] = {"source_url": "https://example.org/x.tif?X-Amz-Signature=abc123&X-Amz-Expires=60"}


def _todo_citation(d: Path, m: Manifest) -> None:
    m["citation"] = "TODO_FILL_IN"


def _role_quantity_mismatch(d: Path, m: Manifest) -> None:
    m.update(role="EARTH_MINERAL", quantity="ELEVATION")


def _units_not_for_quantity(d: Path, m: Manifest) -> None:
    m["units"] = "K"


def _km_declared_but_metres(d: Path, m: Manifest) -> None:
    m["units"] = "km"  # values are ~100..160 m but declared km => 100 000+ m relief


def _unknown_key(d: Path, m: Manifest) -> None:
    m["surprise"] = 1


def _traversal_path(d: Path, m: Manifest) -> None:
    m["files"][0]["path"] = "../dem.tif"
    m["primary_file"] = "../dem.tif"


def _hdf5_missing_variable(d: Path, m: Manifest) -> None:
    m["variable"] = "mineral_metadata/does_not_exist"


def _declared_wrong_format(d: Path, m: Manifest) -> None:
    m["format"] = "ASCII_GRID"


def _zip_with(members: dict[str, bytes], **kw: Any) -> Callable[[Path, Manifest], None]:
    def edit(d: Path, m: Manifest) -> None:
        (d / "N36W112.hgt.zip").unlink()
        b.write_zip(d / "N36W112.hgt.zip", members, **kw)

    return edit


def _zip_bomb(d: Path, m: Manifest) -> None:
    (d / "N36W112.hgt.zip").unlink()
    with zipfile.ZipFile(d / "N36W112.hgt.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("N36W112.hgt", bytes(1201 * 1201 * 2))  # ~2.9 MB of zeros compresses > 20x


def _oversize(d: Path, m: Manifest) -> None:
    return None


CASES: list[tuple[str, str, Callable[[Path, Manifest], None], str, dict[str, Any]]] = [
    # (id, builder, edit, expected failing check_id, ingest kwargs)
    ("schema-missing-crs", "geotiff_earth", _drop("crs"), "manifest_schema", {}),
    ("schema-unknown-key", "geotiff_earth", _unknown_key, "manifest_schema", {}),
    ("schema-traversal-path", "geotiff_earth", _traversal_path, "manifest_schema", {}),
    ("files-missing", "geotiff_earth", _delete_data, "files_present", {}),
    ("files-symlink-escape", "geotiff_earth", _symlink_escape, "files_present", {}),
    ("files-too-large", "geotiff_earth", _oversize, "files_present", {"max_download_bytes": 100}),
    ("checksum-differs", "geotiff_earth", _bad_sha, "checksums", {}),
    ("format-garbage", "geotiff_earth", _garbage_tif, "format_readable", {}),
    ("format-wrong-declared", "geotiff_earth", _declared_wrong_format, "format_readable", {}),
    ("format-hdf5-variable", "netcdf_emit", _hdf5_missing_variable, "format_readable", {}),
    (
        "archive-traversal",
        "hgt_zip",
        _zip_with({"../evil.hgt": b"xx"}),
        "format_readable",
        {},
    ),
    ("archive-nested", "hgt_zip", _zip_with({"inner.zip": b"PK\x03\x04junk"}), "format_readable", {}),
    ("archive-symlink", "hgt_zip", _zip_with({}, symlink=("link.hgt", "/etc/passwd")), "format_readable", {}),
    ("archive-expansion", "hgt_zip", _zip_bomb, "format_readable", {}),
    ("html-login", "geotiff_earth", _html_as_tif, "html_login_page", {}),
    ("crs-missing-in-file", "geotiff_earth", _no_crs, "crs_resolved", {}),
    ("crs-earth-on-mars", "geotiff_mars_scaled", _earth_crs_on_mars, "crs_resolved", {}),
    ("body-wrong-radius", "geotiff_mars_scaled", _planetary_wkt_wrong_radius, "body_consistent", {}),
    ("units-radius-as-elevation", "geotiff_earth", _radius_as_elevation, "units_and_quantity", {}),
    ("units-km-for-metres", "geotiff_earth", _km_declared_but_metres, "units_and_quantity", {}),
    ("units-role-mismatch", "geotiff_earth", _role_quantity_mismatch, "units_and_quantity", {}),
    ("units-unit-for-quantity", "geotiff_earth", _units_not_for_quantity, "units_and_quantity", {}),
    ("scale-double", "geotiff_mars_scaled", _double_scale, "scale_offset_once", {}),
    ("scale-file-not-declared", "geotiff_mars_scaled", _file_scale_not_declared, "scale_offset_once", {}),
    ("scale-claimed-but-absent", "geotiff_earth", _claims_reader_scale_but_none, "scale_offset_once", {}),
    ("nodata-sentinel", "geotiff_earth", _sentinel_without_nodata, "nodata_declared", {}),
    ("nodata-zero-border", "geotiff_earth", _zero_border, "nodata_declared", {}),
    ("transform-south-up", "geotiff_earth", _south_up, "transform_sane", {}),
    ("transform-rotated", "geotiff_earth", _rotated, "transform_sane", {}),
    ("resolution-50pct", "geotiff_earth", _wrong_resolution, "resolution_cross_check", {}),
    ("valid-fraction-none", "geotiff_earth", _all_nodata, "valid_fraction", {}),
    ("longitude-zero360-on-neg", "hgt_pair", _hgt_zero_360, "longitude_convention", {}),
    ("longitude-projected-geographic", "hgt_pair", _projected_on_geographic, "longitude_convention", {}),
    ("longitude-neg180-on-east", "geotiff_mars_scaled", _mars_neg180, "longitude_convention", {}),
    ("lineage-blank-license", "geotiff_earth", _blank_license, "lineage_fields", {}),
    ("lineage-signed-url", "geotiff_earth", _signed_url, "lineage_fields", {}),
    ("lineage-todo-citation", "geotiff_earth", _todo_citation, "lineage_fields", {}),
]


@pytest.mark.parametrize(("name", "kind", "edit", "check_id", "kw"), CASES, ids=[c[0] for c in CASES])
def test_one_failing_fixture_per_check(
    tmp_path: Path, name: str, kind: str, edit: Callable[[Path, Manifest], None], check_id: str, kw: dict[str, Any]
) -> None:
    manifest = build(tmp_path, kind)
    edit(tmp_path / manifest["dataset_id"], manifest)
    result = run(tmp_path, manifest, **kw)
    got = status(result)
    assert got[check_id] == "FAIL", (name, [(c.check_id, c.status, c.message) for c in result.checks])
    # never short-circuits and never raises: all fifteen checks are reported, in order, as a successful computation
    assert [c.check_id for c in result.checks] == list(ck.CHECK_IDS)
    assert result.usable_for_quantitative_claims is False
    assert result.payload is not None and not result.payload.usable_for_quantitative_claims
    assert result.payload.normalized_evidence is None or result.raster is not None
    msg = next(c.message for c in result.checks if c.check_id == check_id)
    assert msg and "Traceback" not in msg


# Cases where the named check is the ONLY failure (the dataset slot rehearsal depends on exactness).
EXACT = {
    "files-missing", "checksum-differs", "html-login", "crs-missing-in-file", "body-wrong-radius",
    "units-radius-as-elevation", "scale-double", "nodata-sentinel", "nodata-zero-border", "transform-south-up",
    "resolution-50pct", "valid-fraction-none", "lineage-blank-license", "lineage-signed-url", "lineage-todo-citation",
    "longitude-neg180-on-east", "units-role-mismatch", "scale-file-not-declared",
}  # fmt: skip


@pytest.mark.parametrize(
    ("name", "kind", "edit", "check_id", "kw"), [c for c in CASES if c[0] in EXACT], ids=sorted(EXACT)
)
def test_named_check_is_the_only_failure(
    tmp_path: Path, name: str, kind: str, edit: Callable[[Path, Manifest], None], check_id: str, kw: dict[str, Any]
) -> None:
    manifest = build(tmp_path, kind)
    edit(tmp_path / manifest["dataset_id"], manifest)
    result = run(tmp_path, manifest, **kw)
    expected = {check_id}
    if name == "files-missing":
        expected = {"files_present"}
    only_fails(result, *expected)


def test_failed_manifest_still_reports_identity_and_every_check(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    del manifest["crs"]
    r = run(tmp_path, manifest)
    assert r.manifest is None and r.payload is not None
    assert (r.payload.dataset_id, r.payload.body, r.payload.role) == ("test-earth-dem", "EARTH", "EARTH_TERRAIN")
    not_evaluated = [c for c in r.checks if c.message.startswith(ck.NOT_EVALUATED)]
    assert len(not_evaluated) == 14 and all(c.status == "WARN" for c in not_evaluated)  # unknown is never PASS


def test_unreadable_directory_raises_blocked_error(tmp_path: Path) -> None:
    with pytest.raises(DatasetUnreadableError):
        ingest_local_dataset(tmp_path / "missing", {}, tmp_path / "scratch")


def test_html_page_detection_is_by_content_not_extension(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    d = tmp_path / manifest["dataset_id"]
    (d / "dem.tif").write_bytes(b"\xef\xbb\xbf  \n" + b.html_login_page())  # BOM + whitespace prefix
    r = run(tmp_path, manifest)
    assert status(r)["html_login_page"] == "FAIL"
    fmt = next(c for c in r.checks if c.check_id == "format_readable")
    assert fmt.status == "WARN" and fmt.message.startswith(ck.NOT_EVALUATED)
    assert "dem.tif" in next(c.message for c in r.checks if c.check_id == "html_login_page")
    assert ck.looks_like_html(b"<!doctype html>") and not ck.looks_like_html(b"II*\x00")


# ------------------------------------------------------------------------------------------------ usable rules
def test_resolution_and_valid_fraction_warns_do_not_block(tmp_path: Path) -> None:
    m1 = build(tmp_path, "geotiff_earth")
    _slight_resolution_error(tmp_path / m1["dataset_id"], m1)
    r1 = run(tmp_path, m1)
    assert status(r1)["resolution_cross_check"] == "WARN" and r1.usable_for_quantitative_claims
    m2 = b.build_geotiff_earth(tmp_path, "test-earth-sparse")
    _mostly_nodata(tmp_path / "test-earth-sparse", m2)
    r2 = run(tmp_path, m2)
    assert status(r2)["valid_fraction"] == "WARN" and r2.usable_for_quantitative_claims
    assert r2.payload is not None and r2.payload.valid_fraction == pytest.approx(0.3)


def test_unknown_pixel_registration_warns_but_does_not_block(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest["pixel_registration"] = "UNKNOWN"
    r = run(tmp_path, manifest)
    assert status(r)["transform_sane"] == "WARN" and r.usable_for_quantitative_claims


def test_not_evaluated_warn_blocks_quantitative_use(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    (tmp_path / manifest["dataset_id"] / "dem.tif").write_bytes(b.html_login_page())
    assert run(tmp_path, manifest).usable_for_quantitative_claims is False


def test_context_only_and_slope_products_are_never_quantitative(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest.update(role="CONTEXT_ONLY", quantity="OTHER", units="dimensionless")
    r = run(tmp_path, manifest)
    assert r.failed == () and r.usable_for_quantitative_claims is False
    assert any("CONTEXT_ONLY" in n for n in r.limitations)
    slope = b.build_geotiff_earth(tmp_path, "test-earth-slope")
    slope.update(quantity="SLOPE_DEG", units="deg")
    _rewrite_tif(tmp_path / "test-earth-slope", "dem.tif", data=np.full((20, 20), 5.0, dtype="float32"))
    r2 = run(tmp_path, slope)
    assert status(r2)["units_and_quantity"] == "WARN" and r2.usable_for_quantitative_claims is False


def test_synthetic_flag_is_carried_into_limitations_and_product_id(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    r = run(tmp_path, manifest)
    assert r.product_id == "SYNTHETIC_TEST_EARTH_DEM"
    assert any("SYNTHETIC" in n for n in r.limitations)


# ------------------------------------------------------------------------------------------------ SCN-14 planetary
def test_moon_polar_wedge_bbox_contains_pole_and_full_longitude_range(tmp_path: Path) -> None:
    manifest = build(tmp_path, "moon_polar_thermal")
    r = run(tmp_path, manifest)
    assert r.failed == () and r.payload is not None and r.payload.bbox_lonlat is not None
    west, south, east, north = r.payload.bbox_lonlat
    assert (west, east) == (-180.0, 180.0) and south == -90.0
    # corner of the 16 km square at (8 km, 8 km) is sqrt(2)*8 km from the pole: colatitude = 11.314/1737.4 rad
    colat = np.degrees(np.hypot(8000.0, 8000.0) / 1737400.0)
    assert north == pytest.approx(-90.0 + colat, abs=0.01)
    assert r.payload.native_resolution_m == pytest.approx(1000.0)
    assert r.raster is not None and np.isnan(r.raster.values[0, 0])  # nodata 0 K is missing, not a temperature


def test_polar_data_is_not_validated_against_an_earth_crs(tmp_path: Path) -> None:
    manifest = build(tmp_path, "moon_polar_thermal")
    manifest["crs"] = {"wkt": b.EARTH_UTM.to_wkt()}
    r = run(tmp_path, manifest)
    assert status(r)["crs_resolved"] == "FAIL" and status(r)["body_consistent"] == "FAIL"


def _moon_wrap_dataset(root: Path, west: float, convention: str, dataset_id: str) -> Manifest:
    d = root / dataset_id
    d.mkdir(parents=True)
    data = b.ramp(8, 8).astype("float32")
    b._gtiff(
        d / "wrap.tif",
        data,
        crs=rasterio.crs.CRS.from_wkt(b.MOON_GEO_WKT),
        transform=from_origin(west, 1.0, 0.025, 0.25),
        nodata=-32768,
    )
    return b.base_manifest(
        dataset_id, body="MOON", role="TARGET_TERRAIN", format="GEOTIFF",
        files=[{"path": "wrap.tif", "role": "DATA"}], primary_file="wrap.tif", quantity="ELEVATION", units="m",
        nodata_value=-32768, vertical_reference="Lunar reference sphere", crs={"wkt": b.MOON_GEO_WKT},
        longitude_convention=convention, latitude_type="PLANETOCENTRIC",
    )  # fmt: skip


def test_longitude_wrap_359_9_to_0_1_is_valid_zero360_and_invalid_neg180(tmp_path: Path) -> None:
    ok = _moon_wrap_dataset(tmp_path, 359.9, "ZERO_360", "wrap-ok")
    r = run(tmp_path, ok)
    assert status(r)["longitude_convention"] == "PASS" and r.failed == ()
    assert r.payload is not None and r.payload.bbox_lonlat is not None
    assert r.payload.bbox_lonlat[0] == pytest.approx(359.9) and r.payload.bbox_lonlat[2] == pytest.approx(360.1)
    bad = _moon_wrap_dataset(tmp_path, 359.9, "NEG180_180", "wrap-bad")
    assert status(run(tmp_path, bad))["longitude_convention"] == "FAIL"
    east = _moon_wrap_dataset(tmp_path, -0.1, "ZERO_360", "wrap-neg")
    assert status(run(tmp_path, east))["longitude_convention"] == "FAIL"
    neg = _moon_wrap_dataset(tmp_path, -0.1, "NEG180_180", "wrap-neg-ok")
    assert status(run(tmp_path, neg))["longitude_convention"] == "PASS"


# ------------------------------------------------------------------------------------------------ purity / determinism
def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


def test_ingest_is_deterministic_and_does_not_modify_the_dataset(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_mars_scaled")
    d = tmp_path / manifest["dataset_id"]
    before = _tree(d)
    a = run(tmp_path, manifest)
    c = ingest_local_dataset(d, copy.deepcopy(manifest), tmp_path / "scratch2")
    assert _tree(d) == before
    assert (
        a.payload == c.payload and a.manifest_sha256 == c.manifest_sha256 and dict(a.file_hashes) == dict(c.file_hashes)
    )
    assert a.raster is not None and c.raster is not None and a.raster.values_sha256 == c.raster.values_sha256
    assert set(a.file_hashes) == {"mola.tif"} and a.file_hashes["mola.tif"] == file_sha256(d / "mola.tif")


def test_evidence_draft_naming_and_parameter_hash_sensitivity(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    r = run(tmp_path, manifest)
    draft = source_evidence_draft(r, mode="synthetic", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)
    assert draft.kind == "SOURCE" and draft.artifact_key is None and draft.source_uri is None
    assert draft.dataset_product_id == "SYNTHETIC_TEST_EARTH_DEM" and draft.local_key == "source-test-earth-dem"
    with pytest.raises(ScienceError):  # a synthetic dataset may never become live evidence
        source_evidence_draft(r, mode="live", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)
    d = tmp_path / manifest["dataset_id"]
    _rewrite_tif(d, "dem.tif", data=b.ramp(20, 20).astype("float32") + 1)
    r2 = run(tmp_path, manifest)
    draft2 = source_evidence_draft(r2, mode="synthetic", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)
    assert draft2.parameters_sha256 != draft.parameters_sha256  # every file hash is in the parameters
    bad = run(tmp_path, {**manifest, "crs": {"epsg": 32612}, "files": []})
    with pytest.raises(ScienceError):
        source_evidence_draft(bad, mode="synthetic", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)


# ------------------------------------------------------------------------------------------------ scaffolding
FILL = {
    "provider": "SYNTHETIC_TEST",
    "license_note": "SYNTHETIC TEST DATA",
    "citation": "AnalogForge tests (synthetic)",
    "vertical_reference": "synthetic datum",
}


def _scaffold(tmp_path: Path, kind: str) -> tuple[Manifest, Manifest]:
    good = build(tmp_path, kind)
    d = tmp_path / good["dataset_id"]
    draft = draft_manifest(d, good["body"], good["role"], scratch_dir=tmp_path / "scaffold-scratch")
    return good, draft


@pytest.mark.parametrize("kind", sorted(b.GOOD_BUILDERS))
def test_draft_fails_until_completed_then_validates(tmp_path: Path, kind: str) -> None:
    good, draft = _scaffold(tmp_path, kind)
    assert draft["provider"] == "TODO_FILL_IN" and draft["license_note"] == "TODO_FILL_IN"
    assert draft["citation"] == "TODO_FILL_IN"
    assert "vertical_reference" in has_unfilled_fields(draft) or draft["vertical_reference"] == "not applicable"
    first = run(tmp_path, draft)
    assert status(first)["lineage_fields"] == "FAIL" and not first.usable_for_quantitative_claims
    filled = copy.deepcopy(draft)
    filled.update(FILL)
    filled["is_synthetic"] = True
    result = run(tmp_path, filled)
    assert result.failed == (), [(c.check_id, c.message) for c in result.checks if c.status == "FAIL"]
    assert result.usable_for_quantitative_claims
    for key in ("format", "quantity", "units", "primary_file"):
        if not (kind == "hgt_pair" and key == "primary_file"):  # multi-tile: any tile may be primary
            assert draft[key] == good[key], key


def test_draft_infers_radius_scale_variable_and_longitude(tmp_path: Path) -> None:
    _, pds = _scaffold(tmp_path, "pds3_radius")
    assert (pds["quantity"], pds["units"], pds["reference_radius_m"]) == ("RADIUS", "km", 1737400.0)
    assert pds["scale_already_applied"] is True and pds["nodata_value"] == -32768
    _, mars = _scaffold(tmp_path, "geotiff_mars_scaled")
    assert mars["longitude_convention"] == "ZERO_360" and mars["scale_factor"] == 0.5 and "wkt" in mars["crs"]
    _, nc = _scaffold(tmp_path, "netcdf_emit")
    assert nc["variable"] == "mineral_metadata/group_1_mineral_id" and nc["crs"] == {"epsg": 4326}
    _, hgt = _scaffold(tmp_path, "hgt_pair")
    assert [f["path"] for f in hgt["files"]] == ["N36W111.hgt", "N36W112.hgt"] and hgt["nodata_value"] == -32768
    assert hgt["declared_native_resolution_m"] == pytest.approx(92.6, abs=0.1)


def test_draft_for_unreadable_files_omits_unknowns_and_never_writes(tmp_path: Path) -> None:
    d = tmp_path / "broken-set"
    d.mkdir()
    (d / "dem.tif").write_bytes(b"junk")
    before = _tree(d)
    draft = draft_manifest(d, "EARTH", "EARTH_TERRAIN")
    assert "crs" not in draft and any("could not be read" in n for n in draft["notes"])
    assert _tree(d) == before and not list(tmp_path.glob(".scaffold*"))
    assert yaml.safe_load(dump_draft_yaml(draft))["provider"] == "TODO_FILL_IN"
    assert status(run(tmp_path, {**draft, "dataset_id": "broken-set"}))["manifest_schema"] == "FAIL"
    with pytest.raises(RegistryError):
        draft_manifest(tmp_path / "NOT_VALID", "EARTH", "EARTH_TERRAIN")


# ------------------------------------------------------------------------------------------------ registry / locks
def test_registry_resolution_listing_and_manifest_loading(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    manifest = b.GOOD_BUILDERS["geotiff_earth"](incoming)
    (incoming / "Bad_Name").mkdir()
    (incoming / "nasa-dem").mkdir()
    (incoming / manifest["dataset_id"] / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    assert list_dataset_ids(incoming) == ["nasa-dem", "test-earth-dem"]
    reg = DatasetRegistry(incoming, tmp_path / "locks")
    assert reg.dataset_dir("test-earth-dem") == incoming / "test-earth-dem"
    assert reg.manifest("test-earth-dem")["dataset_id"] == "test-earth-dem"
    assert run_loaded(reg, "test-earth-dem", tmp_path).failed == ()
    for bad in ("../x", "A", "ab", "x" * 70, "has space"):
        with pytest.raises(RegistryError):
            validate_dataset_id(bad)
    with pytest.raises(DatasetUnreadableError):
        resolve_dataset_dir(incoming, "absent-set")
    (incoming / "escape").symlink_to(tmp_path)
    with pytest.raises(RegistryError):
        resolve_dataset_dir(incoming, "escape")
    (incoming / "nasa-dem" / "manifest.yaml").write_text(
        "!!python/object/apply:os.system ['echo hi']", encoding="utf-8"
    )
    with pytest.raises(DatasetUnreadableError):
        load_manifest_file(incoming / "nasa-dem")
    (incoming / "nasa-dem" / "manifest.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(DatasetUnreadableError):
        load_manifest_file(incoming / "nasa-dem")


def run_loaded(reg: DatasetRegistry, dataset_id: str, tmp_path: Path) -> IngestResult:
    return ingest_local_dataset(reg.dataset_dir(dataset_id), reg.manifest(dataset_id), tmp_path / "scratch")


def test_scratch_write_guard_refuses_incoming_and_outside(tmp_path: Path) -> None:
    scratch, incoming = tmp_path / "scratch", tmp_path / "incoming"
    scratch.mkdir()
    incoming.mkdir()
    assert assert_scratch_write_allowed(scratch / "a.bin", scratch, incoming)
    with pytest.raises(RegistryError):
        assert_scratch_write_allowed(incoming / "a.bin", scratch, incoming)
    with pytest.raises(RegistryError):
        assert_scratch_write_allowed(tmp_path / "elsewhere.bin", scratch, incoming)


def test_lock_build_hash_and_integrity_detection(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    m1, m2 = b.build_geotiff_earth(incoming), b.build_ascii_grid(incoming)
    for m in (m1, m2):  # a locked dataset lives with its manifest.yaml; the lock covers that file too
        (incoming / m["dataset_id"] / "manifest.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    r1, r2 = (ingest_local_dataset(incoming / m["dataset_id"], m, tmp_path / "s") for m in (m1, m2))
    lock = build_lock(
        "local-practice-policy-v1", "2026-11-05T00:00:00Z",
        [lock_entry(r2, incoming / m2["dataset_id"]), lock_entry(r1, incoming / m1["dataset_id"])],
    )  # fmt: skip
    assert [e.dataset_id for e in lock.datasets] == ["test-ascii", "test-earth-dem"]  # sorted: input-order stable
    assert lock.policy_sha256 is not None and lock_is_consistent(lock)
    assert lock_to_bytes(lock) == lock_to_bytes(
        build_lock(lock.policy_id, lock.created_at, list(reversed(lock.datasets)))
    )
    assert all(e.validation == "PASS" and e.usable_for_quantitative_claims for e in lock.datasets)
    assert verify_lock_integrity(lock, incoming) == []
    tif = incoming / "test-earth-dem" / "dem.tif"
    blob = bytearray(tif.read_bytes())
    blob[-1] ^= 0xFF  # flip one byte after locking
    tif.write_bytes(bytes(blob))
    problems = verify_lock_integrity(lock, incoming)
    assert [(p.dataset_id, p.path, p.reason) for p in problems] == [
        ("test-earth-dem", "dem.tif", "SOURCE_CHECKSUM_MISMATCH")
    ]
    (incoming / "test-ascii" / "dem.asc").unlink()
    assert {p.reason for p in verify_lock_integrity(lock, incoming)} == {"SOURCE_CHECKSUM_MISMATCH", "MISSING"}
    tampered = lock.model_copy(update={"allow_network": True})
    assert not lock_is_consistent(tampered)


def test_lock_refuses_datasets_with_failed_checks(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    _wrong_resolution(tmp_path / manifest["dataset_id"], manifest)
    r = run(tmp_path, manifest)
    with pytest.raises(RegistryError):
        lock_entry(r, tmp_path / manifest["dataset_id"])
    broken = {k: v for k, v in manifest.items() if k != "crs"}
    with pytest.raises(RegistryError):
        lock_entry(run(tmp_path, broken), tmp_path / manifest["dataset_id"])


# ---------------------------------------------------------------------------------------------- hardening (review)
def _earth_with_voids(root: Path, declared: float | None, file_nodata: float | None = None) -> Manifest:
    manifest = build(root, "geotiff_earth")
    d = root / manifest["dataset_id"]
    data = b.ramp(20, 20).astype("float32")
    data[2, 3] = -32768  # voids that the declaration does not name
    data[10, 10] = -32768
    _rewrite_tif(d, "dem.tif", data=data, nodata=file_nodata)
    manifest["nodata_value"] = declared
    return manifest


def test_wrong_declared_nodata_with_undeclared_voids_fails(tmp_path: Path) -> None:
    manifest = _earth_with_voids(tmp_path, declared=-9999.0)
    r = run(tmp_path, manifest)
    assert status(r)["nodata_declared"] == "FAIL" and not r.usable_for_quantitative_claims
    assert "-32768" in next(c.message for c in r.checks if c.check_id == "nodata_declared")
    wrong_file = _earth_with_voids(tmp_path / "b", declared=None, file_nodata=-9999.0)
    r2 = run(tmp_path / "b", wrong_file)
    assert status(r2)["nodata_declared"] == "FAIL"


def test_correct_declared_nodata_still_passes_the_sentinel_scan(tmp_path: Path) -> None:
    manifest = _earth_with_voids(tmp_path, declared=-32768.0, file_nodata=-32768.0)
    assert status(run(tmp_path, manifest))["nodata_declared"] == "PASS"


def test_nodata_check_scans_sentinels_other_than_the_declared_one() -> None:
    raw = np.array([[1.0, -32768.0], [2.0, 3.0]])
    assert ck.check_nodata_declared(-9999.0, None, [raw]).status == "FAIL"
    assert ck.check_nodata_declared(-32768.0, None, [raw]).status == "PASS"
    assert ck.check_nodata_declared(-9999.0, None, None).status == "PASS"  # declared and unreadable: nothing to scan


def _nasa_url_manifest(url: str) -> Manifest:
    return {
        "provider": "NASA LP DAAC", "is_synthetic": False, "license_note": "NASA open", "citation": "c",
        "vertical_reference": "EGM96", "product_identity": {"product_id": "NASADEM_HGT", "source_url": url},
    }  # fmt: skip


SECRET_URLS = [
    "https://e.nasa.gov/f.tif#access_token=SECRET",
    "https://e.nasa.gov/f.tif#token=SECRET&x=1",
    "https://e.nasa.gov/f.tif?password=SECRET",
    "https://e.nasa.gov/f.tif?apikey=SECRET",
    "https://e.nasa.gov/f.tif?pwd=SECRET",
    "https://e.nasa.gov/f.tif?sv=2020&se=2030&sp=r&sr=b&sig=SECRET",
    "https://e.nasa.gov/f.tif?X-Amz-Security-Token=SECRET",
    "https://u:SECRET@e.nasa.gov/f.tif",
]


@pytest.mark.parametrize("url", SECRET_URLS)
def test_credential_like_source_url_fails_lineage_and_never_reaches_evidence(tmp_path: Path, url: str) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest.update(_nasa_url_manifest(url))
    r = run(tmp_path, manifest)
    assert status(r)["lineage_fields"] == "FAIL" and not r.usable_for_quantitative_claims
    draft = source_evidence_draft(r, mode="live", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)
    assert draft.source_uri is not None and "SECRET" not in draft.source_uri
    assert "#" not in draft.source_uri and "@" not in draft.source_uri


def test_benign_query_and_fragment_are_stripped_from_the_evidence_uri(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest.update(_nasa_url_manifest("https://e.nasa.gov/f.tif?version=3#section"))
    r = run(tmp_path, manifest)
    assert status(r)["lineage_fields"] == "PASS"
    draft = source_evidence_draft(r, mode="live", algorithm_version="1.0.0", algorithm_config_sha256="a" * 64)
    assert draft.source_uri == "https://e.nasa.gov/f.tif"  # query and fragment are not part of the identity


def _geographic_mars(root: Path, west: float, north: float, step: float, convention: str = "ZERO_360") -> Manifest:
    manifest = build(root, "geotiff_mars_scaled")
    d = root / manifest["dataset_id"]
    raw = (np.arange(24 * 24).reshape(24, 24) % 400 + 200).astype("int16")
    raw[0, 0] = -32768
    b._gtiff(
        d / "mola.tif", raw, crs=rasterio.crs.CRS.from_wkt(b.MARS_GEO_WKT),
        transform=from_origin(west, north, step, step), nodata=-32768, scale=0.5, offset=-100.0,
    )  # fmt: skip
    manifest["longitude_convention"] = convention
    manifest.pop("declared_native_resolution_m", None)
    return manifest


@pytest.mark.parametrize(
    ("north", "step"),
    [(100.0, 0.25), (90.2, 0.25), (95.0, 0.5), (-87.0, 0.25), (10.0, 100.0)],
    ids=["north-100", "north-90.2", "north-95", "south-beyond-minus-90", "huge-cell"],
)
def test_latitudes_beyond_the_poles_fail_transform_without_raising(tmp_path: Path, north: float, step: float) -> None:
    manifest = _geographic_mars(tmp_path, 10.0, north, step)
    r = run(tmp_path, manifest)  # must not raise a pydantic ValidationError (NaN native resolution)
    assert status(r)["transform_sane"] == "FAIL" and not r.usable_for_quantitative_claims
    assert "latitude" in next(c.message for c in r.checks if c.check_id == "transform_sane")
    assert r.payload is not None
    if r.payload.native_resolution_m is not None:
        assert np.isfinite(r.payload.native_resolution_m)


def test_latitudes_inside_the_poles_and_exactly_at_them_pass(tmp_path: Path) -> None:
    ok = _geographic_mars(tmp_path, 10.0, 90.0, 0.25)
    assert status(run(tmp_path, ok))["transform_sane"] == "PASS"


@pytest.mark.parametrize(
    ("convention", "west", "expected"),
    [
        ("ZERO_360", 360.0, "FAIL"),
        ("NEG180_180", 180.0, "FAIL"),
        ("ZERO_360", 359.0, "PASS"),
        ("NEG180_180", -180.0, "PASS"),
    ],
)
def test_longitude_start_outside_the_declared_domain_is_rejected(
    tmp_path: Path, convention: str, west: float, expected: str
) -> None:
    manifest = _geographic_mars(tmp_path, west, 10.0, 0.25, convention)
    assert status(run(tmp_path, manifest))["longitude_convention"] == expected


def test_positive_west_declaration_contradicting_a_positive_east_raster_fails(tmp_path: Path) -> None:
    manifest = _geographic_mars(tmp_path, 10.0, 10.0, 0.25)
    manifest["longitude_direction"] = "POSITIVE_WEST"
    r = run(tmp_path, manifest)
    assert status(r)["longitude_convention"] == "FAIL" and not r.usable_for_quantitative_claims
    assert "POSITIVE_WEST" in next(c.message for c in r.checks if c.check_id == "longitude_convention")


def test_reference_radius_tolerance_is_a_tenth_of_a_percent(tmp_path: Path) -> None:
    base = build(tmp_path, "pds3_radius")
    moon = 1_737_400.0
    for ref, expected in [(moon, "PASS"), (moon * 1.0009, "PASS"), (moon * 1.0011, "FAIL"), (1_750_000.0, "FAIL")]:
        m = copy.deepcopy(base)
        m["reference_radius_m"] = ref
        got = status(run(tmp_path, m))["units_and_quantity"]
        assert got == expected, (ref, got)
    mars = DatasetManifestCopy(base, body="MARS")
    for ref, expected in [(3_396_190.0, True), (3_396_190.0 * 1.0009, True), (3_396_190.0 * 1.0011, False)]:
        out = ck.check_units_and_quantity(mars.model_copy(update={"reference_radius_m": ref}), None)
        assert (out.status != "FAIL") is expected, (ref, out)


def DatasetManifestCopy(raw: Manifest, **update: Any) -> Any:  # noqa: N802 - tiny builder
    from analogforge.ports.datasets import DatasetManifest

    return DatasetManifest.model_validate(raw).model_copy(update=update)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xef\xbb\xbf<!DOCTYPE html><html>",
        b"<!-- login --><html><body>sign in",
        b'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml">',
        b"<!-- a --> <!-- b -->\n<!DOCTYPE html>",
        "<html><body>x".encode("utf-16"),
        "<html><body>x".encode("utf-16-le"),
        b" " * 700 + b"<html>",
    ],
    ids=["bom", "comment", "xml-prolog", "two-comments", "utf16-bom", "utf16-le", "late-html"],
)
def test_html_disguised_as_data_is_detected(tmp_path: Path, payload: bytes) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    (tmp_path / manifest["dataset_id"] / "dem.tif").write_bytes(payload)
    r = run(tmp_path, manifest)
    assert status(r)["html_login_page"] == "FAIL" and not r.usable_for_quantitative_claims


def test_nul_byte_in_a_manifest_file_path_fails_files_present(tmp_path: Path) -> None:
    manifest = build(tmp_path, "geotiff_earth")
    manifest["files"][0]["path"] = "dem\x00.tif"
    manifest["primary_file"] = "dem\x00.tif"
    r = run(tmp_path, manifest)
    assert status(r)["files_present"] in ("FAIL",) or status(r)["manifest_schema"] == "FAIL"
    assert not r.usable_for_quantitative_claims


def _lock_fixture(tmp_path: Path) -> tuple[Path, Manifest, Any]:
    incoming = tmp_path / "incoming"
    manifest = b.build_geotiff_earth(incoming)
    d = incoming / manifest["dataset_id"]
    (d / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    result = ingest_local_dataset(d, load_manifest_file(d), tmp_path / "s")
    lock = build_lock("pol-v1", "2026-11-05T00:00:00Z", [lock_entry(result, d)])
    assert verify_lock_integrity(lock, incoming) == []
    return incoming, manifest, lock


def test_lock_integrity_detects_a_tampered_manifest_even_when_files_are_intact(tmp_path: Path) -> None:
    incoming, manifest, lock = _lock_fixture(tmp_path)
    tampered = {**manifest, "scale_factor": 1000.0, "units": "km", "nodata_value": None}
    (incoming / manifest["dataset_id"] / "manifest.yaml").write_text(yaml.safe_dump(tampered), encoding="utf-8")
    problems = verify_lock_integrity(lock, incoming)
    assert [(p.path, p.reason) for p in problems] == [("manifest.yaml", "SOURCE_CHECKSUM_MISMATCH")]
    (incoming / manifest["dataset_id"] / "manifest.yaml").unlink()
    assert [(p.path, p.reason) for p in verify_lock_integrity(lock, incoming)] == [("manifest.yaml", "MISSING")]
    (incoming / manifest["dataset_id"] / "manifest.yaml").write_text("- not\n- a mapping\n", encoding="utf-8")
    assert [p.reason for p in verify_lock_integrity(lock, incoming)] == ["SOURCE_CHECKSUM_MISMATCH"]


def test_lock_integrity_rejects_symlinked_files_and_dataset_directories(tmp_path: Path) -> None:
    incoming, manifest, lock = _lock_fixture(tmp_path)
    d = incoming / manifest["dataset_id"]
    outside = tmp_path / "outside.tif"
    outside.write_bytes((d / "dem.tif").read_bytes())  # same bytes: a hash-only check would pass
    (d / "dem.tif").unlink()
    (d / "dem.tif").symlink_to(outside)
    assert [(p.path, p.reason) for p in verify_lock_integrity(lock, incoming)] == [("dem.tif", "SYMLINK")]
    (d / "dem.tif").unlink()
    outside.rename(d / "dem.tif")
    assert verify_lock_integrity(lock, incoming) == []
    moved = tmp_path / "moved"
    d.rename(moved)
    d.symlink_to(moved, target_is_directory=True)
    assert {p.reason for p in verify_lock_integrity(lock, incoming)} == {"SYMLINK"}
