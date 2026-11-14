"""The validation checks of architecture 36 section 4, one pure function per ``check_id``.

Every function returns a :class:`CheckOutcome`; none raises for an expected data problem and none depends on the
outcome of another (the orchestrator in :mod:`ingest` always runs all of them, in :data:`CHECK_IDS` order).  A check
that cannot be evaluated because its input does not exist (e.g. no readable raster) reports ``WARN`` with a
``NOT_EVALUATED`` message: never ``PASS`` (unknown is not success) and never ``FAIL`` (the root cause is already
reported by the check that owns it).  ``usable_for_quantitative_claims`` is derived from the outcomes by :func:`usable`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import numpy as np
from numpy.typing import NDArray
from pydantic import ValidationError
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError

from analogforge.adapters.source_http.sniff import SNIFF_BYTES
from analogforge.adapters.source_http.sniff import looks_like_html as sniff_html
from analogforge.ports.datasets import CrsSpec, DatasetManifest
from analogforge.ports.hashing import file_sha256
from analogforge.ports.science_payloads import ValidationCheck
from analogforge.science.geometry import body_geometry, normalize_longitude

Status = Literal["PASS", "WARN", "FAIL"]
FloatArray = NDArray[np.float64]

CHECK_IDS: Final = (
    "manifest_schema",
    "files_present",
    "checksums",
    "format_readable",
    "html_login_page",
    "crs_resolved",
    "body_consistent",
    "units_and_quantity",
    "scale_offset_once",
    "nodata_declared",
    "transform_sane",
    "resolution_cross_check",
    "valid_fraction",
    "longitude_convention",
    "lineage_fields",
)
MAX_DOWNLOAD_BYTES: Final = 2_147_483_648  # architecture 21: per-asset cap
TODO_MARKER: Final = "TODO_FILL_IN"
BODY_RADIUS_TOLERANCE: Final = 0.01  # CRS ellipsoids (a spheroid may sit ~0.3 % above a body's mean radius)
# A RADIUS product's ``reference_radius_m`` is subtracted from every sample, so an error in it is a height bias of
# the same size.  0.1 % of the mean radius (Moon 1737 m, Mars 3396 m) is already far above any published reference
# sphere/ellipsoid difference this pipeline accepts (Moon 1 737 400 m, Mars 3 396 190 m) and far below a 1 % slip.
REFERENCE_RADIUS_TOLERANCE: Final = 0.001
NOT_EVALUATED: Final = "NOT_EVALUATED"
# Formats whose files must embed a CRS (the others legitimately rely on the manifest CRS).
CRS_EMBEDDED_FORMATS: Final = frozenset({"GEOTIFF", "COG", "HGT", "HGT_ZIP"})
SENTINELS: Final = (-32768.0, -9999.0)
_TOKEN_QUERY_KEYS: Final = (
    "token", "signature", "sig", "x-amz", "x-goog", "access", "key", "auth", "credential", "expires",
    "pass", "pwd", "secret", "session", "bearer", "jwt",
)  # fmt: skip
_TOKEN_QUERY_EXACT: Final = frozenset({"sv", "se", "sp", "sr", "st", "sas", "code", "sign"})  # short SAS-style keys

_ROLE_QUANTITIES: Final[dict[str, frozenset[str]]] = {
    "TARGET_TERRAIN": frozenset({"ELEVATION", "RADIUS", "SLOPE_DEG"}),
    "EARTH_TERRAIN": frozenset({"ELEVATION", "RADIUS", "SLOPE_DEG"}),
    "EARTH_MINERAL": frozenset({"MINERAL_CLASS", "BAND_DEPTH"}),
    "LUNAR_THERMAL": frozenset({"TEMPERATURE_K"}),
}
_QUANTITY_UNITS: Final[dict[str, frozenset[str]]] = {
    "ELEVATION": frozenset({"m", "km"}),
    "RADIUS": frozenset({"m", "km"}),
    "SLOPE_DEG": frozenset({"deg"}),
    "TEMPERATURE_K": frozenset({"K"}),
    "MINERAL_CLASS": frozenset({"class"}),
    "BAND_DEPTH": frozenset({"dimensionless"}),
}


@dataclass(frozen=True)
class CheckOutcome:
    """One check result; ``blocking_warn`` False marks a WARN that does not block quantitative use."""

    check_id: str
    status: Status
    message: str
    blocking_warn: bool = True

    def to_check(self) -> ValidationCheck:
        return ValidationCheck(check_id=self.check_id, status=self.status, message=self.message)


def _ok(check_id: str, message: str) -> CheckOutcome:
    return CheckOutcome(check_id, "PASS", message)


def _fail(check_id: str, message: str) -> CheckOutcome:
    return CheckOutcome(check_id, "FAIL", message)


def not_evaluated(check_id: str, reason: str) -> CheckOutcome:
    return CheckOutcome(check_id, "WARN", f"{NOT_EVALUATED}: {reason}")


# ----------------------------------------------------------------------------------------------- manifest
def check_manifest_schema(raw: Mapping[str, Any]) -> tuple[CheckOutcome, DatasetManifest | None]:
    try:
        manifest = DatasetManifest.model_validate(dict(raw))
    except ValidationError as exc:
        parts = [f"{'.'.join(str(p) for p in e['loc']) or '<manifest>'}: {e['msg']}" for e in exc.errors()[:6]]
        return _fail("manifest_schema", "manifest does not validate: " + "; ".join(parts)), None
    if manifest.scale_factor == 0:
        return _fail("manifest_schema", "scale_factor must be non-zero"), None
    return _ok("manifest_schema", "manifest validates against DatasetManifest"), manifest


def check_files_present(
    manifest: DatasetManifest, dataset_dir: Path, max_bytes: int = MAX_DOWNLOAD_BYTES
) -> tuple[CheckOutcome, dict[str, Path]]:
    """Present files by manifest path; failures name the file."""
    root = dataset_dir.resolve()
    present: dict[str, Path] = {}
    problems: list[str] = []
    for entry in manifest.files:
        candidate = dataset_dir / entry.path
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError, RuntimeError, ValueError):  # ValueError: embedded NUL byte
            problems.append(f"{entry.path}: missing")
            continue
        if root not in resolved.parents:
            problems.append(f"{entry.path}: resolves outside the dataset directory (symlink escape)")
        elif not resolved.is_file():
            problems.append(f"{entry.path}: not a regular file")
        elif resolved.stat().st_size > max_bytes:
            problems.append(f"{entry.path}: {resolved.stat().st_size} bytes exceeds MAX_DOWNLOAD_BYTES {max_bytes}")
        else:
            present[entry.path] = resolved
    if problems:
        return _fail("files_present", "; ".join(problems)), present
    return _ok("files_present", f"{len(present)} listed file(s) present inside the dataset directory"), present


def check_checksums(manifest: DatasetManifest, present: Mapping[str, Path]) -> tuple[CheckOutcome, dict[str, str]]:
    """Hash every present file; compare the recorded ones."""
    hashes = {path: file_sha256(real) for path, real in sorted(present.items())}
    bad = [e.path for e in manifest.files if e.sha256 is not None and e.path in hashes and hashes[e.path] != e.sha256]
    if bad:
        return _fail("checksums", "recorded sha256 differs for: " + ", ".join(bad)), hashes
    recorded = sum(1 for e in manifest.files if e.sha256 is not None)
    if recorded == 0:
        return _ok("checksums", "no sha256 recorded in the manifest (nothing to compare); hashes computed"), hashes
    return _ok("checksums", f"{recorded} recorded sha256 value(s) match"), hashes


def looks_like_html(prefix: bytes) -> bool:
    """Shared sniffer (BOMs, comments, XML prolog, UTF-16/32) from the transport layer."""
    return sniff_html(prefix)


def html_files(manifest: DatasetManifest, present: Mapping[str, Path]) -> list[str]:
    found = []
    for entry in manifest.files:
        real = present.get(entry.path)
        if real is None or entry.role == "DOCUMENTATION":
            continue
        with real.open("rb") as handle:
            if looks_like_html(handle.read(SNIFF_BYTES)):
                found.append(entry.path)
    return found


def check_html_login_page(manifest: DatasetManifest | None, present: Mapping[str, Path]) -> CheckOutcome:
    if manifest is None:
        return not_evaluated("html_login_page", "manifest invalid")
    found = html_files(manifest, present)
    if found:
        return _fail(
            "html_login_page",
            "file(s) begin with <html/<!DOCTYPE (an auth/error page saved as data): " + ", ".join(found),
        )
    return _ok("html_login_page", "no listed data/label file starts with an HTML document")


# ----------------------------------------------------------------------------------------------- CRS
def crs_from_spec(spec: CrsSpec) -> CRS:
    return CRS.from_epsg(spec.epsg) if spec.epsg is not None else CRS.from_wkt(spec.wkt or "")


def semi_major_m(crs: CRS) -> float | None:
    ellipsoid = crs.ellipsoid
    return None if ellipsoid is None else float(ellipsoid.semi_major_metre)


def earth_like(crs: CRS) -> bool:
    a = semi_major_m(crs)
    return a is not None and abs(a - 6378137.0) / 6378137.0 < BODY_RADIUS_TOLERANCE


def check_crs_resolved(manifest: DatasetManifest, file_crs_wkt: str | None, raster_read: bool) -> CheckOutcome:
    try:
        declared = crs_from_spec(manifest.crs)
    except CRSError as exc:
        return _fail("crs_resolved", f"manifest CRS cannot be parsed: {exc}")
    is_earth = manifest.body == "EARTH"
    if semi_major_m(declared) is None:
        return _fail("crs_resolved", "manifest CRS has no ellipsoid")
    if earth_like(declared) != is_earth:
        return _fail(
            "crs_resolved",
            f"manifest CRS is {'an Earth' if earth_like(declared) else 'a planetary'} CRS but body is {manifest.body}",
        )
    if not is_earth and declared.to_epsg(min_confidence=100) is not None:
        return _fail("crs_resolved", "an EPSG-coded CRS cannot describe planetary data")
    if not raster_read:
        return not_evaluated("crs_resolved", "raster could not be read, so the file CRS is unknown")
    if file_crs_wkt is None:
        if manifest.format in CRS_EMBEDDED_FORMATS:
            return _fail("crs_resolved", f"{manifest.format} file carries no CRS (manifest CRS alone is not accepted)")
        return _ok("crs_resolved", f"{manifest.format} carries no CRS; the manifest CRS is used")
    try:
        file_crs = CRS.from_wkt(file_crs_wkt)
    except CRSError as exc:
        return _fail("crs_resolved", f"file CRS cannot be parsed: {exc}")
    fa = semi_major_m(file_crs)
    if fa is None:
        return _fail("crs_resolved", "file CRS has no ellipsoid")
    if earth_like(file_crs) != is_earth:
        return _fail("crs_resolved", f"file CRS ellipsoid (a={fa:.1f} m) contradicts body {manifest.body}")
    da = semi_major_m(declared) or 0.0
    if abs(fa - da) / da > BODY_RADIUS_TOLERANCE:
        return _fail("crs_resolved", f"file CRS ellipsoid a={fa:.1f} m contradicts manifest CRS a={da:.1f} m")
    de, fe = declared.to_epsg(min_confidence=100), file_crs.to_epsg(min_confidence=100)
    if is_earth and de is not None and fe is not None and de != fe:
        return _fail("crs_resolved", f"file CRS EPSG:{fe} differs from manifest EPSG:{de}")
    return _ok("crs_resolved", "manifest and file CRS parse and agree with the body")


def check_body_consistent(manifest: DatasetManifest, file_crs_wkt: str | None) -> CheckOutcome:
    mean = body_geometry(manifest.body).mean_radius_m
    labelled: list[tuple[str, CRS]] = []
    try:
        labelled.append(("manifest", crs_from_spec(manifest.crs)))
        if file_crs_wkt is not None:
            labelled.append(("file", CRS.from_wkt(file_crs_wkt)))
    except CRSError as exc:
        return _fail("body_consistent", f"CRS cannot be parsed: {exc}")
    for label, crs in labelled:
        a = semi_major_m(crs)
        if a is None:
            return _fail("body_consistent", f"{label} CRS has no ellipsoid radius")
        if abs(a - mean) / mean > BODY_RADIUS_TOLERANCE:
            return _fail(
                "body_consistent",
                f"{label} CRS radius {a:.1f} m is more than 1% off {manifest.body} mean radius {mean:.1f} m",
            )
    return _ok("body_consistent", f"CRS radius within 1% of {manifest.body} mean radius {mean:.1f} m")


# ----------------------------------------------------------------------------------------------- scale / units
@dataclass(frozen=True)
class ScaleDecision:
    """The single scale/offset transformation applied (``side`` says who applies it)."""

    scale: float
    offset: float
    side: Literal["NONE", "ANALYSIS", "READER"]
    ambiguous: bool
    message: str


def _identity(scale: float, offset: float) -> bool:
    return scale == 1.0 and offset == 0.0


def decide_scale(manifest: DatasetManifest, reader_scale: float, reader_offset: float) -> ScaleDecision:
    """Compare declared and GDAL-reported scale/offset; apply exactly one of them, once."""
    r_id = _identity(reader_scale, reader_offset)
    m_id = _identity(manifest.scale_factor, manifest.offset)
    reader = (reader_scale, reader_offset)
    declared = (manifest.scale_factor, manifest.offset)
    if manifest.scale_already_applied:
        if not r_id:
            if not m_id and not (
                math.isclose(declared[0], reader[0], rel_tol=1e-9)
                and math.isclose(declared[1], reader[1], rel_tol=1e-9, abs_tol=1e-12)
            ):
                return ScaleDecision(
                    *reader,
                    "READER",
                    True,
                    f"SCALE_DOUBLE_APPLICATION_RISK: manifest {declared} contradicts file {reader}",
                )
            return ScaleDecision(
                *reader,
                "READER",
                False,
                f"scale {reader[0]} offset {reader[1]} from file metadata applied once (reader side)",
            )
        if not m_id:
            return ScaleDecision(
                *declared,
                "ANALYSIS",
                True,
                f"SCALE_DOUBLE_APPLICATION_RISK: scale_already_applied but file has no scale; {declared} never applied",
            )
        return ScaleDecision(1.0, 0.0, "NONE", False, "no scale/offset in file or manifest")
    if not r_id and not m_id:
        return ScaleDecision(
            *reader,
            "READER",
            True,
            f"SCALE_DOUBLE_APPLICATION_RISK: scale in file {reader} and manifest {declared}, not marked applied",
        )
    if not r_id:
        return ScaleDecision(
            *reader,
            "READER",
            True,
            f"SCALE_DOUBLE_APPLICATION_RISK: file scale {reader}; set scale_already_applied: true",
        )
    if not m_id:
        return ScaleDecision(
            *declared,
            "ANALYSIS",
            False,
            f"manifest scale {declared[0]} offset {declared[1]} applied once (analysis side)",
        )
    return ScaleDecision(1.0, 0.0, "NONE", False, "no scale/offset in file or manifest")


def check_scale_offset_once(decision: ScaleDecision) -> CheckOutcome:
    return (
        _fail("scale_offset_once", decision.message)
        if decision.ambiguous
        else _ok("scale_offset_once", decision.message)
    )


def _finite(a: FloatArray) -> FloatArray:
    return a[np.isfinite(a)]


def check_units_and_quantity(manifest: DatasetManifest, physical: FloatArray | None) -> CheckOutcome:
    """``physical``: metres of height for ELEVATION/RADIUS, else scaled values (NaN missing)."""
    q, u, role = manifest.quantity, manifest.units, manifest.role
    problems: list[str] = []
    if q == "OTHER":
        if role != "CONTEXT_ONLY":
            problems.append("quantity OTHER is only valid for role CONTEXT_ONLY")
    else:
        if u not in _QUANTITY_UNITS[q]:
            problems.append(f"units {u!r} do not fit quantity {q}")
        allowed = _ROLE_QUANTITIES.get(role)
        if allowed is not None and q not in allowed:
            problems.append(f"role {role} cannot be fed by quantity {q}")
    if q == "RADIUS":
        ref = manifest.reference_radius_m
        mean = body_geometry(manifest.body).mean_radius_m
        if ref is None or abs(ref - mean) / mean > REFERENCE_RADIUS_TOLERANCE:
            problems.append(
                f"reference_radius_m {ref} is not within {REFERENCE_RADIUS_TOLERANCE:.1%} of the "
                f"{manifest.body} mean radius {mean:.1f} m"
            )
    if physical is not None and not problems:
        v = _finite(physical)
        if v.size == 0:
            return not_evaluated("units_and_quantity", "no valid values to assess (see valid_fraction)")
        elif q in ("ELEVATION", "RADIUS"):
            p99 = float(np.percentile(np.abs(v), 99))
            if p99 > 50_000.0:
                hint = (
                    "values look like a radius labelled as elevation"
                    if q == "ELEVATION"
                    else "values do not look like radii in the declared unit"
                )
                problems.append(f"relative height p99 {p99:.4g} m is physically absurd ({hint})")
        elif q == "TEMPERATURE_K":
            if float(v.min()) < 0.0 or float(v.max()) > 1000.0:
                problems.append(f"temperature range [{v.min():.4g}, {v.max():.4g}] K is not physical")
        elif q == "MINERAL_CLASS":
            if not manifest.scale_factor == 1.0 or manifest.offset != 0.0:
                problems.append("class ids cannot be scaled")
            if np.any(v != np.round(v)):
                problems.append("class ids are not integers")
        elif q == "BAND_DEPTH":
            if float(v.min()) < 0.0 or float(v.max()) > 1.0:
                problems.append(f"band depth range [{v.min():.4g}, {v.max():.4g}] outside [0, 1]")
        elif q == "SLOPE_DEG" and (float(v.min()) < 0.0 or float(v.max()) > 90.0):
            problems.append(f"slope range [{v.min():.4g}, {v.max():.4g}] deg outside [0, 90]")
    if problems:
        return _fail("units_and_quantity", "; ".join(problems))
    if physical is None:
        return not_evaluated(
            "units_and_quantity", "raster could not be read; declared quantity/units are consistent with the role only"
        )
    if q == "SLOPE_DEG":
        return CheckOutcome(
            "units_and_quantity",
            "WARN",
            "SLOPE_DEG is pre-derived: allowed but flagged (not independently derived from elevation)",
        )
    return _ok("units_and_quantity", f"{q} in {u} is consistent with role {role} and plausible in magnitude")


# ----------------------------------------------------------------------------------------------- nodata / transform
def _sentinel_problems(raws: Sequence[NDArray[Any]], declared: Sequence[float]) -> list[str]:
    """Known void sentinels present in the raw values that no declaration names (declared values are excluded)."""
    problems: list[str] = []
    for index, raw in enumerate(raws):
        arr = np.asarray(raw)
        for sentinel in SENTINELS:
            if any(math.isclose(sentinel, d) for d in declared):
                continue
            if np.any(arr == sentinel):
                problems.append(f"tile {index}: sentinel value {sentinel:g} present")
    return problems


def check_nodata_declared(
    manifest_nodata: float | None, file_nodata: float | None, raws: Sequence[NDArray[Any]] | None
) -> CheckOutcome:
    """A declared nodata must name the voids that are really in the data.

    Known void sentinels (:data:`SENTINELS`) that are present in the raw values but not named by the manifest/file
    declaration FAIL even when *some* nodata is declared (a wrong declaration lets voids flow in as heights).
    All-zero borders are an undeclared-nodata heuristic and are only examined when nothing is declared.
    """
    if manifest_nodata is not None and file_nodata is not None and not math.isclose(manifest_nodata, file_nodata):
        return _fail("nodata_declared", f"manifest nodata {manifest_nodata} conflicts with file nodata {file_nodata}")
    declared = [v for v in (manifest_nodata, file_nodata) if v is not None]
    if declared:
        side = "manifest" if manifest_nodata is not None else "file"
        text = f"nodata {declared[0]} declared by the {side}"
        if raws is None:
            return _ok("nodata_declared", text)
        stray = _sentinel_problems(raws, declared)
        if stray:
            return _fail("nodata_declared", f"{text} but undeclared void sentinel(s) in the data: " + "; ".join(stray))
        return _ok("nodata_declared", text)
    if raws is None:
        return not_evaluated("nodata_declared", "raster could not be read, cannot scan for sentinel values")
    problems = _sentinel_problems(raws, ())
    for index, raw in enumerate(raws):
        arr = np.asarray(raw)
        if arr.ndim == 2 and min(arr.shape) >= 2:
            borders = {
                "first row": arr[0, :],
                "last row": arr[-1, :],
                "first column": arr[:, 0],
                "last column": arr[:, -1],
            }
            problems += [f"tile {index}: {name} is all zero" for name, line in borders.items() if np.all(line == 0)]
    if problems:
        return _fail("nodata_declared", "no nodata declared but " + "; ".join(problems))
    return _ok("nodata_declared", "no nodata declared and no sentinel values or all-zero border found")


LATITUDE_EPS: Final = 1e-6


def check_transform_sane(
    gt: tuple[float, float, float, float, float, float] | None,
    registration: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> CheckOutcome:
    """Geotransform sanity; ``bbox`` (W, S, E, N degrees, cell extents included) must stay on the globe."""
    if gt is None:
        return not_evaluated("transform_sane", "raster could not be read")
    _, a, b, _, d, e = gt
    if not all(math.isfinite(x) for x in gt):
        return _fail("transform_sane", "geotransform has non-finite entries")
    if a * e - b * d == 0.0:
        return _fail("transform_sane", "geotransform is not invertible")
    if bbox is not None and not all(math.isfinite(x) for x in bbox):
        return _fail("transform_sane", "raster extent cannot be expressed in degrees (non-finite bounds)")
    if bbox is not None and (bbox[1] < -90.0 - LATITUDE_EPS or bbox[3] > 90.0 + LATITUDE_EPS):
        return _fail(
            "transform_sane", f"latitude extent {bbox[1]:.6g}..{bbox[3]:.6g} deg (cell edges included) exceeds +-90"
        )
    if abs(b) > 1e-9 * abs(a) or abs(d) > 1e-9 * abs(e):
        return _fail("transform_sane", f"rotated geotransform (b={b}, d={d}) is not supported")
    if e > 0:
        return _fail("transform_sane", f"positive y pixel size ({e}): south-up raster must be flipped explicitly")
    if a < 0:
        return _fail("transform_sane", f"negative x pixel size ({a}) is not supported")
    if registration == "UNKNOWN":
        return CheckOutcome(
            "transform_sane",
            "WARN",
            "pixel_registration UNKNOWN (recorded; blocks only sub-pixel control-point claims)",
            blocking_warn=False,
        )
    return _ok("transform_sane", f"north-up, unrotated, invertible; pixel_registration {registration}")


def check_resolution_cross_check(declared_m: float | None, derived_m: float | None) -> CheckOutcome:
    if derived_m is None:
        return not_evaluated("resolution_cross_check", "native resolution could not be derived")
    if declared_m is None:
        return _ok("resolution_cross_check", f"no declared resolution; derived posting {derived_m:.4g} m")
    rel = abs(declared_m - derived_m) / declared_m
    text = f"declared {declared_m:.4g} m vs derived {derived_m:.4g} m ({rel:.1%} apart)"
    if rel > 0.5:
        return _fail("resolution_cross_check", text)
    if rel > 0.05:
        return CheckOutcome("resolution_cross_check", "WARN", text, blocking_warn=False)
    return _ok("resolution_cross_check", text)


def check_valid_fraction(fraction: float | None) -> CheckOutcome:
    if fraction is None:
        return not_evaluated("valid_fraction", "raster could not be read")
    text = f"valid fraction {fraction:.4f}"
    if fraction < 0.05:
        return _fail("valid_fraction", text + " < 0.05")
    if fraction < 0.5:
        return CheckOutcome("valid_fraction", "WARN", text + " < 0.5", blocking_warn=False)
    return _ok("valid_fraction", text)


# ----------------------------------------------------------------------------------------------- longitude
def lonlat_bbox(
    crs: CRS, gt: tuple[float, float, float, float, float, float], height: int, width: int, convention: str
) -> tuple[float, float, float, float]:
    """(west, south, east, north) in degrees (geographic: the extent; projected: inverse-projected)."""
    x0, a, _, y0, _, e = gt
    x1, y1 = x0 + width * a, y0 + height * e
    xmin, xmax, ymin, ymax = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    if crs.is_geographic:
        return (xmin, ymin, xmax, ymax)
    conv = "ZERO_360" if convention == "ZERO_360" else "NEG180_180"
    inverse = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    t = np.linspace(0.0, 1.0, 41)
    xs = np.concatenate([xmin + (xmax - xmin) * t, np.full(41, xmax), xmax - (xmax - xmin) * t, np.full(41, xmin)])
    ys = np.concatenate([np.full(41, ymin), ymin + (ymax - ymin) * t, np.full(41, ymax), ymax - (ymax - ymin) * t])
    lon, lat = inverse.transform(xs, ys)
    lon_a, lat_a = np.asarray(lon, dtype=np.float64), np.asarray(lat, dtype=np.float64)
    forward = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    for pole in (90.0, -90.0):
        px, py = forward.transform(0.0, pole)
        if math.isfinite(px) and math.isfinite(py) and xmin <= px <= xmax and ymin <= py <= ymax:
            lo, hi = (-180.0, 180.0) if conv == "NEG180_180" else (0.0, 360.0)
            return (lo, -90.0, hi, float(lat_a.max())) if pole < 0 else (lo, float(lat_a.min()), hi, 90.0)
    centre = math.degrees(
        math.atan2(float(np.mean(np.sin(np.radians(lon_a)))), float(np.mean(np.cos(np.radians(lon_a)))))
    )
    rel = ((lon_a - centre + 180.0) % 360.0) - 180.0
    lo = centre + float(rel.min())
    hi = centre + float(rel.max())
    lo_n = normalize_longitude(lo, conv)  # type: ignore[arg-type]
    return (lo_n, float(lat_a.min()), lo_n + (hi - lo), float(lat_a.max()))


def _longitude_axis_direction(crs: CRS) -> str | None:
    """``east``/``west`` for the longitude axis of a geographic CRS (None when it cannot be told)."""
    for axis in crs.axis_info:
        if axis.abbrev.lower() in ("lon", "long", "longitude") or axis.name.lower().startswith("longitude"):
            return str(axis.direction).lower() if str(axis.direction).lower() in ("east", "west") else None
    return None


def check_longitude_convention(
    manifest: DatasetManifest,
    crs: CRS | None,
    bbox: tuple[float, float, float, float] | None,
    pixel_deg: float | None,
) -> CheckOutcome:
    if crs is None or bbox is None:
        return not_evaluated("longitude_convention", "raster extent unavailable")
    conv = manifest.longitude_convention
    if conv == "PROJECTED":
        if crs.is_geographic:
            return _fail("longitude_convention", "declared PROJECTED but the raster CRS is geographic")
        return _ok("longitude_convention", "PROJECTED convention with a projected CRS")
    if not crs.is_geographic:
        return _ok(
            "longitude_convention", f"projected CRS; longitude range {bbox[0]:.4f}..{bbox[2]:.4f} normalised to {conv}"
        )
    eps = 0.5 * (pixel_deg or 0.0) + 1e-9
    west, east = bbox[0], bbox[2]
    axis = _longitude_axis_direction(crs)
    declared_direction = "west" if manifest.longitude_direction == "POSITIVE_WEST" else "east"
    if axis is not None and axis != declared_direction:
        return _fail(
            "longitude_convention",
            f"manifest longitude_direction {manifest.longitude_direction} contradicts the raster CRS, whose "
            f"longitude axis is positive-{axis}; the pipeline never mirrors longitudes",
        )
    lo, hi = (-180.0, 180.0) if conv == "NEG180_180" else (0.0, 360.0)
    # An unwrapped raster may spill past the upper bound when it starts inside the range (antimeridian crossing).
    # The start must lie inside the half-open domain [lo, hi): 360 is not a ZERO_360 start and 180 not a NEG180_180 one.
    if west < lo - eps or west >= hi - 1e-9 or east - west > 360.0 + eps:
        return _fail(
            "longitude_convention",
            f"raster longitudes {west:.4f}..{east:.4f} contradict declared {conv} ({lo:g}..{hi:g})",
        )
    return _ok("longitude_convention", f"raster longitudes {west:.4f}..{east:.4f} agree with {conv}")


# ----------------------------------------------------------------------------------------------- lineage
def _placeholder(text: str | None) -> bool:
    return text is None or not text.strip() or TODO_MARKER in text


def _credential_keys(pairs: Sequence[tuple[str, str]]) -> bool:
    keys = [k.lower() for k, _ in pairs]
    return any(k in _TOKEN_QUERY_EXACT or any(t in k for t in _TOKEN_QUERY_KEYS) for k in keys)


def credential_like_url(url: str) -> bool:
    """True when ``url`` carries userinfo, or credential-like parameter names in its query or fragment."""
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for an invalid port
    except ValueError:
        return True  # an unparseable URL is never accepted as a lineage identity
    if parts.username or parts.password:
        return True
    return any(
        _credential_keys(parse_qsl(piece, keep_blank_values=True)) for piece in (parts.query, parts.fragment) if piece
    )


def sanitized_source_url(url: str | None) -> str | None:
    """The URL as it may appear in evidence: scheme, host[:port] and path only.

    Userinfo, query and fragment are dropped (the evidence registrar refuses a query string or credentials, and a
    fragment/query can carry a token); the query is never part of a source's identity here.
    """
    if url is None:
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
    except ValueError:
        return None
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def check_lineage_fields(manifest: DatasetManifest) -> CheckOutcome:
    problems = [
        name
        for name, value in (
            ("license_note", manifest.license_note),
            ("citation", manifest.citation),
            ("provider", manifest.provider),
            ("vertical_reference", manifest.vertical_reference),
            ("title", manifest.title),
        )
        if _placeholder(value)
    ]
    url = manifest.product_identity.source_url
    if url is not None and credential_like_url(url):
        problems.append("product_identity.source_url (signed, token-bearing or credential-carrying)")
    if problems:
        return _fail("lineage_fields", "empty or placeholder lineage field(s): " + ", ".join(problems))
    return _ok("lineage_fields", "license_note, citation, provider and vertical_reference are filled")


# ----------------------------------------------------------------------------------------------- verdict
def usable(manifest: DatasetManifest | None, outcomes: Sequence[CheckOutcome]) -> bool:
    """architecture 36 section 4: every check passed, tolerating only the documented non-blocking WARNs."""
    if manifest is None or manifest.role == "CONTEXT_ONLY":
        return False
    return all(o.status == "PASS" or (o.status == "WARN" and not o.blocking_warn) for o in outcomes)


__all__ = [
    "CHECK_IDS",
    "MAX_DOWNLOAD_BYTES",
    "NOT_EVALUATED",
    "SENTINELS",
    "TODO_MARKER",
    "CheckOutcome",
    "ScaleDecision",
    "check_body_consistent",
    "check_checksums",
    "check_crs_resolved",
    "check_files_present",
    "check_html_login_page",
    "check_lineage_fields",
    "check_longitude_convention",
    "credential_like_url",
    "check_manifest_schema",
    "check_nodata_declared",
    "check_resolution_cross_check",
    "check_scale_offset_once",
    "check_transform_sane",
    "check_units_and_quantity",
    "check_valid_fraction",
    "crs_from_spec",
    "decide_scale",
    "earth_like",
    "html_files",
    "lonlat_bbox",
    "looks_like_html",
    "not_evaluated",
    "sanitized_source_url",
    "semi_major_m",
    "usable",
]
