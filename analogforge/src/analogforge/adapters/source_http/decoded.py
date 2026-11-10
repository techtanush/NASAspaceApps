"""Normalized decode result shared by every adapter decoder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

Affine6 = tuple[float, float, float, float, float, float]  # a, b, c, d, e, f (GDAL pixel-edge convention)


@dataclass(frozen=True)
class RasterMetadata:
    """Canonical raster metadata (architecture 09 section 5) for one decoded product."""

    adapter_id: str
    body: str  # EARTH | MOON | MARS
    quantity: str  # orthometric_height | relative_height | radius | brightness_temperature | mineral_id | ...
    units: str
    vertical_reference: str | None
    crs_wkt: str | None
    transform: Affine6 | None  # pixel-edge affine mapping (col,row) -> (x,y) in crs units (degrees if geographic)
    width: int
    height: int
    pixel_registration: str
    longitude_domain: str | None = None
    nodata_raw: float | None = None
    source_scale: float | None = None
    source_offset: float | None = None
    scale_applied: bool = False
    product_id: str | None = None
    notes: tuple[str, ...] = ()
    attributes: Mapping[str, str] = field(default_factory=dict)
    quantitative_use_allowed: bool = True
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecodedRaster:
    """``data`` is float64 with NaN where invalid for continuous quantities (never 0) or an integer id
    array for categorical quantities; ``valid`` is the authoritative validity mask."""

    data: NDArray[Any]
    valid: NDArray[np.bool_]
    metadata: RasterMetadata
    aux: Mapping[str, NDArray[Any]] = field(default_factory=dict)
    dictionary: Mapping[int, str] = field(default_factory=dict)

    @property
    def valid_fraction(self) -> float:
        return float(self.valid.sum()) / float(self.valid.size) if self.valid.size else 0.0


def geographic_wkt(name: str, a_radius_m: float, b_radius_m: float | None = None) -> str:
    """WKT2 geographic CRS on a body-specific sphere/ellipsoid. Never an Earth datum for another body."""
    a = float(a_radius_m)
    b = float(b_radius_m if b_radius_m is not None else a_radius_m)
    ell = f'ELLIPSOID["{name} ellipsoid",{a:.6f},{(a / (a - b)) if a != b else 0:.12g},LENGTHUNIT["metre",1]]'
    return (
        f'GEOGCRS["{name} geographic",DATUM["{name} datum",{ell}],PRIMEM["Reference Meridian",0],'
        'CS[ellipsoidal,2],AXIS["longitude",east,ORDER[1]],AXIS["latitude",north,ORDER[2]],'
        'ANGLEUNIT["degree",0.0174532925199433]]'
    )
