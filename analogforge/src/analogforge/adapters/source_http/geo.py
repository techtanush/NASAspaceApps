"""Longitude-domain aware bounding-box helpers (planar degrees; no Earth CRS is implied for other bodies)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from shapely.geometry import box
from shapely.ops import unary_union

from analogforge.adapters.source_http.errors import AdapterError

Box = tuple[float, float, float, float]  # west, south, east, north


def validate_bbox(bbox: Sequence[float]) -> Box:
    if len(bbox) != 4:
        raise AdapterError("NO_COVERAGE", "bbox must be [west, south, east, north]", detail_code="INPUT_INVALID")
    west, south, east, north = (float(v) for v in bbox)
    if west == east:  # zero-width (a full circle is expressed as west + 360 = east, e.g. 0..360 or -180..180)
        raise AdapterError("NO_COVERAGE", "bbox has zero width (west == east)", detail_code="INPUT_INVALID")
    if not (-90.0 <= south < north <= 90.0):
        raise AdapterError(
            "NO_COVERAGE", "bbox latitudes must satisfy -90 <= south < north <= 90", detail_code="INPUT_INVALID"
        )
    return west, south, east, north


def split_bbox(bbox: Sequence[float], source_convention: str, target_convention: str) -> list[Box]:
    """Express ``bbox`` in the ``target_convention`` longitude domain, splitting at the domain seam.

    Conventions are ``NEG180_180`` or ``ZERO_360``. A box with west > east wraps through the seam of its own
    convention. Result boxes always have west <= east, are sorted, and never exceed the target domain.
    """
    west, south, east, north = validate_bbox(bbox)
    if source_convention == "NEG180_180" and not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
        raise AdapterError("NO_COVERAGE", "longitude outside -180..180", detail_code="INPUT_INVALID")
    if source_convention == "ZERO_360" and not (0.0 <= west <= 360.0 and 0.0 <= east <= 360.0):
        raise AdapterError("NO_COVERAGE", "longitude outside 0..360", detail_code="INPUT_INVALID")
    width = east - west if east >= west else east - west + 360.0
    if width >= 360.0 - 1e-12:
        lo, hi = (-180.0, 180.0) if target_convention == "NEG180_180" else (0.0, 360.0)
        return [(lo, south, hi, north)]
    if target_convention == "NEG180_180":
        w = ((west + 180.0) % 360.0) - 180.0
        lo, hi = -180.0, 180.0
    else:
        w = west % 360.0
        lo, hi = 0.0, 360.0
    e = w + width
    if e <= hi:
        return [(w, south, e, north)]
    return [(w, south, hi, north), (lo, south, e - 360.0, north)]


def coverage_fraction(aoi_pieces: Iterable[Box], product_boxes: Iterable[Box]) -> float:
    """Planar-degree fraction of the AOI covered by the union of ``product_boxes`` (0..1).

    A product box with west > east wraps through the seam of its domain (0/360 when any longitude exceeds 180, else
    -180/180) and is split there.  A box with west == east is empty.
    """
    aoi = unary_union([box(w, s, e, n) for w, s, e, n in aoi_pieces])
    if aoi.is_empty or aoi.area <= 0.0:
        return 0.0
    domain_hi = 360.0 if any(max(b[0], b[2]) > 180.0 for b in [*aoi_pieces, *product_boxes]) else 180.0
    domain_lo = 0.0 if domain_hi == 360.0 else -180.0
    prods = []
    for w, s, e, n in product_boxes:
        if n <= s:
            continue
        if e > w:
            prods.append(box(w, s, e, n))
        elif e < w:  # west > east: the footprint crosses the seam of its longitude domain
            prods += [box(w, s, domain_hi, n), box(domain_lo, s, e, n)]
    if not prods:
        return 0.0
    inter = aoi.intersection(unary_union(prods))
    return float(min(1.0, max(0.0, inter.area / aoi.area)))


def to_cmr_bounding_boxes(bbox: Sequence[float], source_convention: str) -> list[str]:
    return [f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}" for w, s, e, n in split_bbox(bbox, source_convention, "NEG180_180")]
