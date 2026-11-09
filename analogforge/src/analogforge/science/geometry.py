"""Body-aware geometry: ellipsoids, body-specific projections, analysis grids and longitude handling.

Rules (architecture 10 section 2, 29 section 3):

* Every public function takes the body explicitly.  Earth uses WGS84 plus a local UTM/UPS (or declared local
  transverse-Mercator) projection; the Moon and Mars use the planetary sphere with a body-specific
  equirectangular or polar-stereographic projection.  Earth CRS codes are never used for planetary data.
* Distances use the body's own ellipsoid (never an Earth haversine radius).
* Longitudes are normalised for computation but the caller's convention is preserved; AOIs may wrap at 180/360.
* Linear distortion above ``max_linear_distortion`` (default 1 percent) raises ``DISTORTION_EXCEEDED``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from pyproj import CRS, Geod, Proj, Transformer
from pyproj.exceptions import CRSError

from analogforge.ports.common import Body
from analogforge.science.errors import GeometryError

FloatArray = NDArray[np.float64]
LongitudeConvention = Literal["NEG180_180", "ZERO_360"]
LatitudeType = Literal["PLANETOCENTRIC", "PLANETOGRAPHIC", "GEODETIC"]
BBox = tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat), degrees, positive east

WGS84_A_M: Final = 6378137.0
WGS84_INV_F: Final = 298.257223563
MOON_RADIUS_M: Final = 1737400.0  # IAU/IAG Moon 2000 reference sphere
MARS_RADIUS_M: Final = 3396190.0  # Mars 2000 reference sphere
DEFAULT_MAX_LINEAR_DISTORTION: Final = 0.01
POLAR_LATITUDE_DEG: Final = 80.0


# --------------------------------------------------------------------------- body geometry
@dataclass(frozen=True)
class BodyGeometry:
    """Shape of a body used for distances and projections (NOT its gravity)."""

    body: Body
    semi_major_m: float
    semi_minor_m: float
    ellipsoid_name: str
    reference_frame: str

    @property
    def is_sphere(self) -> bool:
        return self.semi_major_m == self.semi_minor_m

    @property
    def flattening(self) -> float:
        return (self.semi_major_m - self.semi_minor_m) / self.semi_major_m

    @property
    def mean_radius_m(self) -> float:
        return (2.0 * self.semi_major_m + self.semi_minor_m) / 3.0

    def geod(self) -> Geod:
        return Geod(a=self.semi_major_m, b=self.semi_minor_m)

    def ellipsoid_proj_args(self) -> str:
        if self.is_sphere:
            return f"+R={self.semi_major_m!r}"
        return f"+a={self.semi_major_m!r} +b={self.semi_minor_m!r}"

    def geographic_crs(self) -> CRS:
        """Geographic CRS on this body's ellipsoid (positive-east longitude, geodetic/planetographic latitude)."""
        if self.body == "EARTH":
            return CRS.from_epsg(4326)
        return CRS.from_proj4(f"+proj=longlat {self.ellipsoid_proj_args()} +no_defs +type=crs")


_EARTH: Final = BodyGeometry("EARTH", WGS84_A_M, WGS84_A_M * (1.0 - 1.0 / WGS84_INV_F), "WGS 84", "ITRF/WGS84")
_MOON: Final = BodyGeometry("MOON", MOON_RADIUS_M, MOON_RADIUS_M, "Moon_2000_IAU_IAG sphere", "IAU Moon 2000")
_MARS: Final = BodyGeometry("MARS", MARS_RADIUS_M, MARS_RADIUS_M, "Mars_2000_IAU_IAG sphere", "IAU Mars 2000")


def body_geometry(body: Body) -> BodyGeometry:
    """Reference ellipsoid of ``body`` (Earth WGS84, Moon 1737.4 km sphere, Mars 3396.19 km sphere)."""
    if body == "EARTH":
        return _EARTH
    if body == "MOON":
        return _MOON
    if body == "MARS":
        return _MARS
    raise GeometryError(f"unknown body {body!r}", detail_code="BODY_MISMATCH")


def body_distance_m(body: Body, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Geodesic distance on the body's own ellipsoid (metres)."""
    _, _, dist = body_geometry(body).geod().inv(lon1, lat1, lon2, lat2)
    return float(dist)


def convert_latitude(lat_deg: float, src: LatitudeType, dst: LatitudeType, geometry: BodyGeometry) -> float:
    """Convert between planetocentric and planetographic/geodetic latitude on ``geometry``.

    On a sphere all three coincide; on an oblate ellipsoid ``tan(phi_c) = (b/a)^2 tan(phi_g)``.
    """
    if not -90.0 <= lat_deg <= 90.0:
        raise GeometryError(f"latitude {lat_deg} outside [-90, 90]", code="INPUT_INVALID")
    centric_src = src == "PLANETOCENTRIC"
    centric_dst = dst == "PLANETOCENTRIC"
    if centric_src == centric_dst or geometry.is_sphere:
        return lat_deg
    ratio = (geometry.semi_minor_m / geometry.semi_major_m) ** 2
    if abs(lat_deg) == 90.0:
        return lat_deg
    tan_lat = math.tan(math.radians(lat_deg))
    out = tan_lat * ratio if centric_dst else tan_lat / ratio
    return math.degrees(math.atan(out))


# --------------------------------------------------------------------------- longitude handling
def normalize_longitude(lon_deg: float, convention: LongitudeConvention) -> float:
    """Normalise to ``[-180, 180)`` (NEG180_180) or ``[0, 360)`` (ZERO_360)."""
    if not math.isfinite(lon_deg):
        raise GeometryError("longitude must be finite", code="INPUT_INVALID")
    if convention == "ZERO_360":
        return lon_deg % 360.0
    return ((lon_deg + 180.0) % 360.0) - 180.0


def to_positive_east(lon_deg: float, direction: Literal["POSITIVE_EAST", "POSITIVE_WEST"]) -> float:
    """Return a positive-east longitude (planetary products may be positive west)."""
    return lon_deg if direction == "POSITIVE_EAST" else -lon_deg


def _validate_bbox(bbox: BBox) -> None:
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise GeometryError("bbox needs four finite numbers", code="INPUT_INVALID")
    if not (-90.0 <= bbox[1] <= bbox[3] <= 90.0):
        raise GeometryError("bbox latitudes must satisfy -90 <= min_lat <= max_lat <= 90", code="INPUT_INVALID")


def unwrap_bbox(bbox: BBox, convention: LongitudeConvention) -> BBox:
    """Return the bbox with a continuous longitude interval ``min_lon <= max_lon`` (may exceed the convention).

    ``[359.9, -1, 0.1, 1]`` in ZERO_360 becomes ``[359.9, -1, 360.1, 1]``; ``[170, .., -170, ..]`` in
    NEG180_180 becomes ``[170, .., 190, ..]``.  A raw span of 360 degrees or more is the full circle.
    """
    _validate_bbox(bbox)
    min_lon, min_lat, max_lon, max_lat = bbox
    if max_lon - min_lon >= 360.0:
        start = normalize_longitude(min_lon, convention)
        return (start, min_lat, start + 360.0, max_lat)
    lo = normalize_longitude(min_lon, convention)
    hi = normalize_longitude(max_lon, convention)
    if hi < lo:
        hi += 360.0
    return (lo, min_lat, hi, max_lat)


def split_bbox_at_antimeridian(bbox: BBox, convention: LongitudeConvention) -> list[BBox]:
    """Split a wrapping bbox into one or two ``NEG180_180`` boxes (Earth discovery needs non-wrapping AOIs)."""
    lo, min_lat, hi, max_lat = unwrap_bbox(bbox, convention)
    if hi - lo >= 360.0:
        return [(-180.0, min_lat, 180.0, max_lat)]
    lo_n = normalize_longitude(lo, "NEG180_180")
    hi_n = lo_n + (hi - lo)
    if hi_n <= 180.0:
        return [(lo_n, min_lat, hi_n, max_lat)]
    return [(lo_n, min_lat, 180.0, max_lat), (-180.0, min_lat, hi_n - 360.0, max_lat)]


def bbox_longitude_centre(bbox: BBox, convention: LongitudeConvention) -> float:
    """Wrap-aware centre longitude of the bbox in the requested convention."""
    lo, _, hi, _ = unwrap_bbox(bbox, convention)
    return normalize_longitude(0.5 * (lo + hi), convention)


# --------------------------------------------------------------------------- projected frames
FrameKind = Literal["UTM", "UPS", "LOCAL_TM", "EQUIRECTANGULAR", "POLAR_STEREOGRAPHIC"]


@dataclass(frozen=True)
class ProjectedFrame:
    """A body-specific metric projection used for all slope/length computations.

    ``crs_wkt`` is the authority; ``epsg`` is set only for Earth frames.  ``max_linear_distortion`` is the maximum
    |scale - 1| sampled over the AOI the frame was built for.
    """

    body: Body
    kind: FrameKind
    crs_wkt: str
    epsg: int | None
    max_linear_distortion: float


@lru_cache(maxsize=64)
def _crs_from_wkt(wkt: str) -> CRS:
    return CRS.from_wkt(wkt)


@lru_cache(maxsize=64)
def _forward_transformer(body: Body, crs_wkt: str) -> Transformer:
    return Transformer.from_crs(body_geometry(body).geographic_crs(), _crs_from_wkt(crs_wkt), always_xy=True)


@lru_cache(maxsize=64)
def _inverse_transformer(body: Body, crs_wkt: str) -> Transformer:
    return Transformer.from_crs(_crs_from_wkt(crs_wkt), body_geometry(body).geographic_crs(), always_xy=True)


def assert_crs_matches_body(body: Body, crs_wkt: str) -> None:
    """Reject an Earth CRS for a planet (and a planetary CRS for Earth) by comparing the ellipsoid.

    This is the guard behind "no Earth CRS for Moon/Mars": EPSG:4326, EPSG:3857, UTM, ... all carry an Earth
    ellipsoid and fail here for a planetary body.
    """
    try:
        crs = _crs_from_wkt(crs_wkt)
    except CRSError as exc:
        raise GeometryError("CRS WKT cannot be parsed", detail_code="FRAME_UNRESOLVED") from exc
    ellipsoid = crs.ellipsoid
    if ellipsoid is None:
        raise GeometryError("CRS has no ellipsoid", detail_code="FRAME_UNRESOLVED")
    geometry = body_geometry(body)
    matches = abs(float(ellipsoid.semi_major_metre) - geometry.semi_major_m) < 1.0
    if not matches:
        raise GeometryError(
            f"CRS ellipsoid (a={ellipsoid.semi_major_metre:.1f} m) does not belong to body {body}",
            detail_code="BODY_MISMATCH",
        )
    if body != "EARTH" and crs.to_epsg(min_confidence=100) is not None:
        raise GeometryError("an EPSG-coded CRS cannot describe planetary data", detail_code="BODY_MISMATCH")


def _sample_lonlat(unwrapped: BBox, n: int = 11) -> tuple[FloatArray, FloatArray]:
    lons = np.linspace(unwrapped[0], unwrapped[2], n)
    lats = np.linspace(unwrapped[1], unwrapped[3], n)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lon_grid.ravel(), lat_grid.ravel()


def _frame_distortion(body: Body, crs_wkt: str, unwrapped: BBox) -> float:
    """Maximum |scale factor - 1| (meridional and parallel) over a sample lattice of the AOI."""
    projection = Proj(_crs_from_wkt(crs_wkt))
    lons, lats = _sample_lonlat(unwrapped)
    worst = 0.0
    for lon, lat in zip(lons, lats, strict=True):
        lat_c = max(min(float(lat), 89.999999), -89.999999)
        factors = projection.get_factors(float(lon), lat_c)
        for scale in (factors.meridional_scale, factors.parallel_scale):
            if not math.isfinite(scale):
                raise GeometryError("projection scale undefined inside the AOI", detail_code="DISTORTION_EXCEEDED")
            worst = max(worst, abs(float(scale) - 1.0))
    return worst


_BODY_LABEL: Final = {"EARTH": "Earth", "MOON": "Moon", "MARS": "Mars"}


def _name_planetary_crs(crs: CRS, body: Body, kind: FrameKind) -> CRS:
    """Give a PROJ-string CRS honest names (body datum/ellipsoid) instead of ``unknown``."""
    label = _BODY_LABEL[body]
    definition = crs.to_json_dict()
    definition["name"] = f"{label} 2000 {kind.lower().replace('_', ' ')}"
    base = definition.get("base_crs")
    if isinstance(base, dict):
        base["name"] = f"{label} 2000"
        datum = base.get("datum")
        if isinstance(datum, dict):
            datum["name"] = f"D_{label}_2000"
            ellipsoid = datum.get("ellipsoid")
            if isinstance(ellipsoid, dict):
                ellipsoid["name"] = f"{label}_2000_IAU_IAG"
    conversion = definition.get("conversion")
    if isinstance(conversion, dict):
        conversion["name"] = kind.lower().replace("_", " ")
    return CRS.from_json_dict(definition)


def _make_frame(
    body: Body, kind: FrameKind, crs: CRS, epsg: int | None, unwrapped: BBox, limit: float
) -> ProjectedFrame:
    if body != "EARTH":
        crs = _name_planetary_crs(crs, body, kind)
    wkt = crs.to_wkt()
    distortion = _frame_distortion(body, wkt, unwrapped)
    if distortion > limit:
        raise GeometryError(
            f"{kind} projection distorts distances by {distortion:.4f} > {limit:.4f} inside the AOI; "
            "use a smaller AOI or a more appropriate projection",
            detail_code="DISTORTION_EXCEEDED",
        )
    return ProjectedFrame(body=body, kind=kind, crs_wkt=wkt, epsg=epsg, max_linear_distortion=distortion)


def projected_frame_for_aoi(
    body: Body,
    bbox: BBox,
    convention: LongitudeConvention = "NEG180_180",
    *,
    max_linear_distortion: float = DEFAULT_MAX_LINEAR_DISTORTION,
) -> ProjectedFrame:
    """Choose and validate a metric projection for an AOI on ``body``.

    * EARTH: the UTM zone of the AOI centre when the AOI lies inside one zone, UPS beyond 84 N / 80 S, otherwise a
      declared local transverse Mercator; always distortion-checked.
    * MOON/MARS: polar stereographic about the nearer pole when the AOI reaches |lat| >= 80, otherwise an
      equirectangular projection centred on the AOI on the body's own sphere.  Never an Earth CRS.
    """
    unwrapped = unwrap_bbox(bbox, convention)
    lon_c = normalize_longitude(0.5 * (unwrapped[0] + unwrapped[2]), "NEG180_180")
    lat_c = 0.5 * (unwrapped[1] + unwrapped[3])
    geometry = body_geometry(body)

    if body == "EARTH":
        extreme = max(abs(unwrapped[1]), abs(unwrapped[3]))
        if unwrapped[3] > 84.0 or unwrapped[1] < -80.0:
            if extreme > 90.0:
                raise GeometryError("latitude out of range", code="INPUT_INVALID")
            north = lat_c >= 0
            epsg = 32661 if north else 32761
            return _make_frame(body, "UPS", CRS.from_epsg(epsg), epsg, unwrapped, max_linear_distortion)
        zones = {
            int(math.floor((normalize_longitude(lon, "NEG180_180") + 180.0) / 6.0)) + 1
            for lon in (unwrapped[0], unwrapped[2])
        }
        if unwrapped[2] - unwrapped[0] < 6.0 and len(zones) == 1:
            zone = zones.pop()
            north = lat_c >= 0
            epsg = (32600 if north else 32700) + zone
            return _make_frame(body, "UTM", CRS.from_epsg(epsg), epsg, unwrapped, max_linear_distortion)
        false_northing = 0.0 if lat_c >= 0 else 10_000_000.0
        proj = (
            f"+proj=tmerc +lat_0=0 +lon_0={lon_c!r} +k=0.9996 +x_0=500000 +y_0={false_northing!r} "
            f"+ellps=WGS84 +units=m +no_defs +type=crs"
        )
        return _make_frame(body, "LOCAL_TM", CRS.from_proj4(proj), None, unwrapped, max_linear_distortion)

    ellipsoid = geometry.ellipsoid_proj_args()
    if max(abs(unwrapped[1]), abs(unwrapped[3])) >= POLAR_LATITUDE_DEG:
        pole = 90.0 if abs(unwrapped[3]) >= abs(unwrapped[1]) else -90.0
        proj = (
            f"+proj=stere +lat_0={pole!r} +lat_ts={pole!r} +lon_0=0 +k=1 +x_0=0 +y_0=0 "
            f"{ellipsoid} +units=m +no_defs +type=crs"
        )
        return _make_frame(body, "POLAR_STEREOGRAPHIC", CRS.from_proj4(proj), None, unwrapped, max_linear_distortion)
    proj = (
        f"+proj=eqc +lat_ts={lat_c!r} +lat_0=0 +lon_0={lon_c!r} +x_0=0 +y_0=0 {ellipsoid} +units=m +no_defs +type=crs"
    )
    return _make_frame(body, "EQUIRECTANGULAR", CRS.from_proj4(proj), None, unwrapped, max_linear_distortion)


def frame_from_crs_wkt(body: Body, crs_wkt: str) -> ProjectedFrame:
    """Wrap a CRS taken from a dataset manifest/label, after checking that it belongs to ``body``."""
    assert_crs_matches_body(body, crs_wkt)
    crs = _crs_from_wkt(crs_wkt)
    if not crs.is_projected:
        raise GeometryError(
            "a projected (metric) CRS is required for derivative computations", detail_code="FRAME_UNRESOLVED"
        )
    epsg = crs.to_epsg(min_confidence=100) if body == "EARTH" else None
    return ProjectedFrame(
        body=body,
        kind="LOCAL_TM" if body == "EARTH" else "EQUIRECTANGULAR",
        crs_wkt=crs.to_wkt(),
        epsg=epsg,
        max_linear_distortion=0.0,
    )


# --------------------------------------------------------------------------- coordinate transforms
def lonlat_to_xy(
    frame: ProjectedFrame, lon: FloatArray | float, lat: FloatArray | float
) -> tuple[FloatArray, FloatArray]:
    """Project positive-east longitude/latitude (degrees) to the frame's metric coordinates."""
    x, y = _forward_transformer(frame.body, frame.crs_wkt).transform(
        np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    )
    return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)


def xy_to_lonlat(
    frame: ProjectedFrame, x: FloatArray | float, y: FloatArray | float, convention: LongitudeConvention = "NEG180_180"
) -> tuple[FloatArray, FloatArray]:
    """Inverse projection; longitudes are normalised to ``convention``."""
    lon, lat = _inverse_transformer(frame.body, frame.crs_wkt).transform(
        np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    )
    lon_arr = np.asarray(lon, dtype=np.float64)
    lon_arr = lon_arr % 360.0 if convention == "ZERO_360" else ((lon_arr + 180.0) % 360.0) - 180.0
    return lon_arr, np.asarray(lat, dtype=np.float64)


def densified_boundary_lonlat(
    bbox: BBox, convention: LongitudeConvention, samples_per_edge: int = 41
) -> tuple[FloatArray, FloatArray]:
    """Boundary of the (unwrapped) bbox sampled densely: polar wedges and curved edges bend in a projection."""
    lo, min_lat, hi, max_lat = unwrap_bbox(bbox, convention)
    t = np.linspace(0.0, 1.0, samples_per_edge)
    lons = np.concatenate(
        [lo + (hi - lo) * t, np.full(samples_per_edge, hi), hi - (hi - lo) * t, np.full(samples_per_edge, lo)]
    )
    lats = np.concatenate(
        [
            np.full(samples_per_edge, min_lat),
            min_lat + (max_lat - min_lat) * t,
            np.full(samples_per_edge, max_lat),
            max_lat - (max_lat - min_lat) * t,
        ]
    )
    return lons, lats


def bbox_to_projected_bounds(
    frame: ProjectedFrame, bbox: BBox, convention: LongitudeConvention = "NEG180_180", samples_per_edge: int = 41
) -> tuple[float, float, float, float]:
    """Projected bounds ``(xmin, ymin, xmax, ymax)`` of a lon/lat bbox via its densified boundary."""
    lons, lats = densified_boundary_lonlat(bbox, convention, samples_per_edge)
    x, y = lonlat_to_xy(frame, lons, lats)
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        raise GeometryError("AOI cannot be projected into the frame", detail_code="FRAME_UNRESOLVED")
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())


def projected_bounds_to_bbox(
    frame: ProjectedFrame,
    bounds: tuple[float, float, float, float],
    convention: LongitudeConvention = "NEG180_180",
    samples_per_edge: int = 41,
) -> BBox:
    """Lon/lat bbox enclosing a projected rectangle (wrap- and pole-aware)."""
    xmin, ymin, xmax, ymax = bounds
    t = np.linspace(0.0, 1.0, samples_per_edge)
    xs = np.concatenate(
        [
            xmin + (xmax - xmin) * t,
            np.full(samples_per_edge, xmax),
            xmax - (xmax - xmin) * t,
            np.full(samples_per_edge, xmin),
        ]
    )
    ys = np.concatenate(
        [
            np.full(samples_per_edge, ymin),
            ymin + (ymax - ymin) * t,
            np.full(samples_per_edge, ymax),
            ymax - (ymax - ymin) * t,
        ]
    )
    lons, lats = xy_to_lonlat(frame, xs, ys, "NEG180_180")
    contains_pole = frame.kind == "POLAR_STEREOGRAPHIC" and xmin <= 0.0 <= xmax and ymin <= 0.0 <= ymax
    if contains_pole:
        south = float(np.mean(lats)) < 0
        lo_lon, hi_lon = (-180.0, 180.0) if convention == "NEG180_180" else (0.0, 360.0)
        return (lo_lon, -90.0 if south else float(lats.min()), hi_lon, float(lats.max()) if south else 90.0)
    # unwrap around the circular mean so an antimeridian-crossing rectangle yields min <= max
    centre = math.degrees(
        math.atan2(float(np.mean(np.sin(np.radians(lons)))), float(np.mean(np.cos(np.radians(lons)))))
    )
    rel = ((lons - centre + 180.0) % 360.0) - 180.0
    lo = centre + float(rel.min())
    hi = centre + float(rel.max())
    lo_n = normalize_longitude(lo, convention)
    hi_n = lo_n + (hi - lo)
    if convention == "NEG180_180" and hi_n > 180.0:
        hi_n -= 360.0
    if convention == "ZERO_360" and hi_n >= 360.0:
        hi_n -= 360.0
    return (lo_n, float(lats.min()), hi_n, float(lats.max()))


# --------------------------------------------------------------------------- pixel geometry and grids
@dataclass(frozen=True)
class PixelGeometry:
    """Metric step (east, north) per column/row step: supports anisotropic and rotated rasters.

    ``x = x0 + col * dx_dcol + row * dx_drow`` and ``y = y0 + col * dy_dcol + row * dy_drow`` (GDAL geotransform
    terms ``a, b`` and ``d, e``).
    """

    dx_dcol: float
    dy_dcol: float
    dx_drow: float
    dy_drow: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(v) for v in (self.dx_dcol, self.dy_dcol, self.dx_drow, self.dy_drow)):
            raise GeometryError("pixel geometry must be finite", code="INPUT_INVALID")
        if self.determinant == 0.0:
            raise GeometryError("pixel geometry is singular", code="INPUT_INVALID")

    @property
    def determinant(self) -> float:
        return self.dx_dcol * self.dy_drow - self.dx_drow * self.dy_dcol

    @property
    def cell_area_m2(self) -> float:
        return abs(self.determinant)

    @classmethod
    def north_up(cls, cell_x_m: float, cell_y_m: float | None = None) -> PixelGeometry:
        """Unrotated raster with rows running south: ``dy/drow = -cell_y``."""
        return cls(cell_x_m, 0.0, 0.0, -(cell_x_m if cell_y_m is None else cell_y_m))

    @classmethod
    def from_geotransform(cls, gt: tuple[float, float, float, float, float, float]) -> PixelGeometry:
        """From a GDAL geotransform ``(x0, a, b, y0, d, e)``."""
        return cls(dx_dcol=gt[1], dy_dcol=gt[4], dx_drow=gt[2], dy_drow=gt[5])

    @classmethod
    def rotated(cls, cell_x_m: float, cell_y_m: float, angle_deg: float) -> PixelGeometry:
        """North-up geometry rotated counter-clockwise by ``angle_deg``."""
        c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
        base = cls.north_up(cell_x_m, cell_y_m)
        return cls(
            dx_dcol=c * base.dx_dcol - s * base.dy_dcol,
            dy_dcol=s * base.dx_dcol + c * base.dy_dcol,
            dx_drow=c * base.dx_drow - s * base.dy_drow,
            dy_drow=s * base.dx_drow + c * base.dy_drow,
        )

    def offset_xy(self, dcol: float, drow: float) -> tuple[float, float]:
        return dcol * self.dx_dcol + drow * self.dx_drow, dcol * self.dy_dcol + drow * self.dy_drow


@dataclass(frozen=True)
class AnalysisGridSpec:
    """North-up square-cell analysis grid in a body-specific projected CRS.

    ``origin_x_m``/``origin_y_m`` are the west edge of column 0 and the north edge of row 0.
    """

    body: Body
    crs_wkt: str
    origin_x_m: float
    origin_y_m: float
    cell_size_m: float
    width: int
    height: int

    def __post_init__(self) -> None:
        if not (math.isfinite(self.origin_x_m) and math.isfinite(self.origin_y_m)):
            raise GeometryError("grid origin must be finite", code="INPUT_INVALID")
        if not (math.isfinite(self.cell_size_m) and self.cell_size_m > 0):
            raise GeometryError("cell_size_m must be positive", code="INPUT_INVALID")
        if self.width < 1 or self.height < 1:
            raise GeometryError("grid needs at least one cell", code="INPUT_INVALID")

    @property
    def cell_area_m2(self) -> float:
        return self.cell_size_m * self.cell_size_m

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(xmin, ymin, xmax, ymax)``."""
        return (
            self.origin_x_m,
            self.origin_y_m - self.height * self.cell_size_m,
            self.origin_x_m + self.width * self.cell_size_m,
            self.origin_y_m,
        )

    @property
    def geotransform(self) -> tuple[float, float, float, float, float, float]:
        """GDAL order ``(x0, dx, 0, y0, 0, -dy)``."""
        return (self.origin_x_m, self.cell_size_m, 0.0, self.origin_y_m, 0.0, -self.cell_size_m)

    def pixel_geometry(self) -> PixelGeometry:
        return PixelGeometry.north_up(self.cell_size_m)

    def cell_centre(self, row: int, col: int) -> tuple[float, float]:
        return (
            self.origin_x_m + (col + 0.5) * self.cell_size_m,
            self.origin_y_m - (row + 0.5) * self.cell_size_m,
        )

    def centre_coordinates(self) -> tuple[FloatArray, FloatArray]:
        """Arrays ``(x, y)`` of every cell centre, shape ``(height, width)``."""
        cols = self.origin_x_m + (np.arange(self.width, dtype=np.float64) + 0.5) * self.cell_size_m
        rows = self.origin_y_m - (np.arange(self.height, dtype=np.float64) + 0.5) * self.cell_size_m
        x, y = np.meshgrid(cols, rows)
        return x, y

    def index_of(self, x: float, y: float) -> tuple[int, int] | None:
        """``(row, col)`` of the cell containing a projected point, or ``None`` when outside the grid."""
        col = math.floor((x - self.origin_x_m) / self.cell_size_m)
        row = math.floor((self.origin_y_m - y) / self.cell_size_m)
        if 0 <= row < self.height and 0 <= col < self.width:
            return (row, col)
        return None

    def window(self, row0: int, col0: int, height: int, width: int) -> AnalysisGridSpec:
        """Sub-grid ``[row0, row0 + height) x [col0, col0 + width)`` (must lie inside this grid)."""
        if row0 < 0 or col0 < 0 or row0 + height > self.height or col0 + width > self.width:
            raise GeometryError("window lies outside the grid", code="INPUT_INVALID")
        return AnalysisGridSpec(
            self.body,
            self.crs_wkt,
            self.origin_x_m + col0 * self.cell_size_m,
            self.origin_y_m - row0 * self.cell_size_m,
            self.cell_size_m,
            width,
            height,
        )

    def aggregated(self, factor: int) -> AnalysisGridSpec:
        """Grid after block aggregation by ``factor`` (trailing partial blocks are dropped)."""
        if factor < 1:
            raise GeometryError("aggregation factor must be >= 1", code="INPUT_INVALID")
        width, height = self.width // factor, self.height // factor
        if width < 1 or height < 1:
            raise GeometryError("grid is smaller than one aggregation block", code="SCALE_INCOMPATIBLE")
        return AnalysisGridSpec(
            self.body, self.crs_wkt, self.origin_x_m, self.origin_y_m, self.cell_size_m * factor, width, height
        )


def grid_from_bounds(
    frame: ProjectedFrame, bounds: tuple[float, float, float, float], cell_size_m: float, *, snap: bool = True
) -> AnalysisGridSpec:
    """Grid covering projected ``bounds``; with ``snap`` the edges are rounded outward to multiples of the cell."""
    xmin, ymin, xmax, ymax = bounds
    if not (xmax > xmin and ymax > ymin):
        raise GeometryError("empty bounds", code="INPUT_INVALID")
    if snap:
        xmin = math.floor(xmin / cell_size_m) * cell_size_m
        ymax = math.ceil(ymax / cell_size_m) * cell_size_m
        xmax = math.ceil(xmax / cell_size_m) * cell_size_m
        ymin = math.floor(ymin / cell_size_m) * cell_size_m
    width = max(1, int(round((xmax - xmin) / cell_size_m)))
    height = max(1, int(round((ymax - ymin) / cell_size_m)))
    return AnalysisGridSpec(frame.body, frame.crs_wkt, xmin, ymax, cell_size_m, width, height)


def grid_for_bbox(
    frame: ProjectedFrame,
    bbox: BBox,
    cell_size_m: float,
    convention: LongitudeConvention = "NEG180_180",
    *,
    snap: bool = True,
) -> AnalysisGridSpec:
    """Analysis grid covering a lon/lat AOI, computed through its densified projected boundary."""
    return grid_from_bounds(frame, bbox_to_projected_bounds(frame, bbox, convention), cell_size_m, snap=snap)


def pixel_to_world_gdal(grid: AnalysisGridSpec) -> tuple[float, float, float, float, float, float]:
    """GDAL-order affine of the grid (pixel corner convention)."""
    return grid.geotransform


def world_to_pixel_continuous(grid: AnalysisGridSpec, x: float, y: float) -> tuple[float, float]:
    """Continuous ``(col, row)`` of a projected point (pixel corner at integer coordinates)."""
    return ((x - grid.origin_x_m) / grid.cell_size_m, (grid.origin_y_m - y) / grid.cell_size_m)


__all__ = [
    "DEFAULT_MAX_LINEAR_DISTORTION",
    "MARS_RADIUS_M",
    "MOON_RADIUS_M",
    "WGS84_A_M",
    "AnalysisGridSpec",
    "BBox",
    "BodyGeometry",
    "LatitudeType",
    "LongitudeConvention",
    "PixelGeometry",
    "ProjectedFrame",
    "assert_crs_matches_body",
    "bbox_longitude_centre",
    "bbox_to_projected_bounds",
    "body_distance_m",
    "body_geometry",
    "convert_latitude",
    "densified_boundary_lonlat",
    "frame_from_crs_wkt",
    "grid_for_bbox",
    "grid_from_bounds",
    "lonlat_to_xy",
    "normalize_longitude",
    "pixel_to_world_gdal",
    "projected_bounds_to_bbox",
    "projected_frame_for_aoi",
    "split_bbox_at_antimeridian",
    "to_positive_east",
    "unwrap_bbox",
    "world_to_pixel_continuous",
    "xy_to_lonlat",
]
