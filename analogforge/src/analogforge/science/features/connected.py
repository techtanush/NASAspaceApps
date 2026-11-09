"""Connected safe zones (8-connectivity) with per-zone band areas.

A histogram across disconnected patches does not prove a continuous test exists (architecture 10 section 7), so
route design works on connected components of the *safe* mask: valid, land, ``slope <= cap``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from analogforge.ports.science_payloads import ConnectedZone
from analogforge.science.errors import RasterError
from analogforge.science.features.histogram import band_label

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int32]

_EIGHT = np.ones((3, 3), dtype=bool)


@dataclass(frozen=True)
class Band:
    """Slope band ``[lo, hi)`` (``[lo, hi]`` when ``upper_inclusive``)."""

    lo: float
    hi: float
    upper_inclusive: bool = False

    @property
    def label(self) -> str:
        return band_label(self.lo, self.hi)

    def contains(self, slope: FloatArray) -> BoolArray:
        upper = slope <= self.hi if self.upper_inclusive else slope < self.hi
        return np.asarray((slope >= self.lo) & upper, dtype=bool)


@dataclass(frozen=True)
class ZoneStats:
    """One connected safe zone (``label`` indexes the label raster returned with it)."""

    zone_id: str
    label: int
    cell_count: int
    area_m2: float
    first_cell: tuple[int, int]  # row-major first cell
    bbox_cells: tuple[int, int, int, int]  # (row_min, col_min, row_max, col_max) inclusive
    band_area_m2: dict[str, float]
    contains_start: bool


def safe_mask(slope_deg: FloatArray, valid: BoolArray, land: BoolArray, cap_deg: float) -> BoolArray:
    """Valid land cells whose surface slope does not exceed ``cap_deg`` (inclusive)."""
    if not (slope_deg.shape == valid.shape == land.shape):
        raise RasterError("slope, valid and land shapes differ")
    with np.errstate(invalid="ignore"):
        return np.asarray(valid & land & (slope_deg <= cap_deg), dtype=bool)


def label_components(mask: BoolArray, connectivity: int = 8) -> tuple[IntArray, int]:
    """Label connected True regions.  4- or 8-connectivity; label 0 is background."""
    if connectivity not in (4, 8):
        raise RasterError("connectivity must be 4 or 8")
    structure = _EIGHT if connectivity == 8 else None
    labels, count = ndimage.label(mask, structure=structure)
    return np.asarray(labels, dtype=np.int32), int(count)


def connected_zones(
    safe: BoolArray,
    slope_deg: FloatArray,
    cell_area_m2: float,
    bands: Sequence[Band] = (),
    *,
    start_cell: tuple[int, int] | None = None,
    min_cells: int = 1,
    connectivity: int = 8,
) -> tuple[list[ZoneStats], IntArray]:
    """Zones sorted by ``(-area, first cell row-major)`` and named ``zone-1``, ``zone-2``, ...

    Returns the zone list and the raw component label raster (use ``ZoneStats.label``).  ``contains_start`` is
    true for the zone holding ``start_cell``.
    """
    if cell_area_m2 <= 0.0:
        raise RasterError("cell area must be positive")
    labels, count = label_components(safe, connectivity)
    start_label = 0
    if start_cell is not None:
        r, c = start_cell
        if not (0 <= r < labels.shape[0] and 0 <= c < labels.shape[1]):
            raise RasterError("start cell outside the raster")
        start_label = int(labels[r, c])
    raw: list[tuple[int, int, tuple[int, int], tuple[int, int, int, int], dict[str, float]]] = []
    for lab in range(1, count + 1):
        cells = labels == lab
        n = int(cells.sum())
        if n < min_cells:
            continue
        rows, cols = np.nonzero(cells)
        first = (int(rows[0]), int(cols[0]))  # np.nonzero is row-major ordered
        bbox = (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max()))
        band_area = {b.label: float((cells & b.contains(slope_deg)).sum()) * cell_area_m2 for b in bands}
        raw.append((lab, n, first, bbox, band_area))
    raw.sort(key=lambda t: (-t[1], t[2]))
    zones = [
        ZoneStats(
            zone_id=f"zone-{i + 1}",
            label=lab,
            cell_count=n,
            area_m2=n * cell_area_m2,
            first_cell=first,
            bbox_cells=bbox,
            band_area_m2=band_area,
            contains_start=(start_label != 0 and lab == start_label),
        )
        for i, (lab, n, first, bbox, band_area) in enumerate(raw)
    ]
    return zones, labels


def largest_component(safe: BoolArray, connectivity: int = 8) -> BoolArray | None:
    """Mask of the largest component; ties go to the smallest row-major first cell.  ``None`` if no safe cell."""
    labels, count = label_components(safe, connectivity)
    if count == 0:
        return None
    best_label = 0
    best_key: tuple[int, int, int] | None = None
    for lab in range(1, count + 1):
        cells = labels == lab
        rows, cols = np.nonzero(cells)
        key = (-int(cells.sum()), int(rows[0]), int(cols[0]))
        if best_key is None or key < best_key:
            best_key, best_label = key, lab
    return np.asarray(labels == best_label, dtype=bool)


def to_port_zone(zone: ZoneStats, bbox_lonlat: tuple[float, float, float, float] | None = None) -> ConnectedZone:
    """Kit :class:`ConnectedZone`."""
    return ConnectedZone(
        zone_id=zone.zone_id,
        area_m2=zone.area_m2,
        band_area_m2=dict(zone.band_area_m2),
        contains_start=zone.contains_start,
        bbox_lonlat=bbox_lonlat,
    )
