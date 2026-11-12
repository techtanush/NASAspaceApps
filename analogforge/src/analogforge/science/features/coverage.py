"""Coverage and quality bookkeeping for analysis rasters.

Quality codes (``quality`` member of the ANALYSIS_GRID) classify every cell with one reason, in precedence order
``OUTSIDE_SOURCE > NODATA > WATER > NO_FULL_SUPPORT > OK``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError

BoolArray = NDArray[np.bool_]
UInt8Array = NDArray[np.uint8]

QUALITY_OK: Final = 0
QUALITY_NODATA: Final = 1
QUALITY_WATER: Final = 2
QUALITY_NO_FULL_SUPPORT: Final = 3
QUALITY_OUTSIDE_SOURCE: Final = 4
QUALITY_LABELS: Final = {
    QUALITY_OK: "valid land with full 3x3 support",
    QUALITY_NODATA: "source nodata or non-finite",
    QUALITY_WATER: "water",
    QUALITY_NO_FULL_SUPPORT: "land lacking full derivative support (raster border or adjacent to nodata/water)",
    QUALITY_OUTSIDE_SOURCE: "outside the source extent",
}


def classify_cells(
    nodata: BoolArray, water: BoolArray, valid: BoolArray, outside_source: BoolArray | None = None
) -> UInt8Array:
    """Per-cell quality code with the documented precedence."""
    if not (nodata.shape == water.shape == valid.shape):
        raise RasterError("classification masks must share one shape")
    quality = np.full(valid.shape, QUALITY_NO_FULL_SUPPORT, dtype=np.uint8)
    quality[valid] = QUALITY_OK
    quality[water] = QUALITY_WATER
    quality[nodata] = QUALITY_NODATA
    if outside_source is not None:
        if outside_source.shape != valid.shape:
            raise RasterError("outside_source mask shape mismatch")
        quality[outside_source] = QUALITY_OUTSIDE_SOURCE
    return quality


@dataclass(frozen=True)
class CoverageSummary:
    """Fractions of the window (all denominators are the full window area)."""

    n_cells: int
    valid_fraction: float  # valid land with full support / window
    water_fraction: float
    nodata_fraction: float
    no_support_fraction: float
    outside_fraction: float

    @property
    def land_data_fraction(self) -> float:
        """Land cells with data (valid or merely lacking full support) / window."""
        return self.valid_fraction + self.no_support_fraction


def coverage_summary(quality: UInt8Array) -> CoverageSummary:
    """Summarize a quality raster.  An empty raster is an error: a missing fraction must stay unknown."""
    n = int(quality.size)
    if n == 0:
        raise RasterError("cannot summarize an empty raster")

    def share(code: int) -> float:
        return float(np.count_nonzero(quality == code)) / n

    return CoverageSummary(
        n_cells=n,
        valid_fraction=share(QUALITY_OK),
        water_fraction=share(QUALITY_WATER),
        nodata_fraction=share(QUALITY_NODATA),
        no_support_fraction=share(QUALITY_NO_FULL_SUPPORT),
        outside_fraction=share(QUALITY_OUTSIDE_SOURCE),
    )


def is_water_only(summary: CoverageSummary, water_only_fraction: float) -> bool:
    """True when the window is (almost) entirely water (``WATER_ONLY`` exclusion)."""
    return summary.water_fraction >= water_only_fraction
