"""In-memory raster sources and GDAL reading.

:class:`SourceRaster` is the canonical hand-over between source resolution (fixtures, local datasets, adapter
output) and the analysis code: elevation in metres on a north-up square-cell grid in a body-specific projected
CRS, with an explicit nodata mask.  :func:`read_gdal_raster` returns *raw* values (GDAL via rasterio never applies
scale/offset here); :func:`resample_to_grid` area-averages them onto an analysis grid and refuses to upsample.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.errors import RasterioError
from rasterio.transform import Affine
from rasterio.warp import reproject

from analogforge.ports.common import Body
from analogforge.science.errors import RasterError, ScaleError
from analogforge.science.geometry import AnalysisGridSpec, body_geometry

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class RawRaster:
    """Raw GDAL band values with their georeference (no scaling or masking applied)."""

    values: NDArray[np.number]
    geotransform: tuple[float, float, float, float, float, float]  # GDAL order x0, a, b, y0, d, e
    crs_wkt: str | None
    nodata_value: float | None
    dtype: str
    driver: str
    reader_scale: float
    reader_offset: float


def read_gdal_raster(path: Path, band: int = 1, variable: str | None = None) -> RawRaster:
    """Read one band raw via rasterio/GDAL.  ``variable`` selects a NetCDF/HDF subdataset."""
    target = f'NETCDF:"{path}":{variable}' if variable else str(path)
    try:
        with rasterio.open(target) as src:
            if not 1 <= band <= src.count:
                raise RasterError(f"band {band} not present (file has {src.count})")
            values = src.read(band)
            transform = src.transform
            return RawRaster(
                values=values,
                geotransform=(transform.c, transform.a, transform.b, transform.f, transform.d, transform.e),
                crs_wkt=None if src.crs is None else src.crs.to_wkt(),
                nodata_value=src.nodata,
                dtype=str(values.dtype),
                driver=str(src.driver),
                reader_scale=float(src.scales[band - 1]),
                reader_offset=float(src.offsets[band - 1]),
            )
    except RasterioError as exc:
        raise RasterError(f"GDAL cannot open {path.name}: {exc}", code="SOURCE_CONTENT_INVALID") from exc


@dataclass(frozen=True)
class SourceRaster:
    """Elevation (m) on a north-up square grid; ``nodata`` marks missing cells (their ``values`` are NaN)."""

    grid: AnalysisGridSpec
    values: FloatArray
    nodata: BoolArray
    native_resolution_m: float
    support_scale_m: float
    vertical_reference: str
    water: BoolArray | None = None
    product_id: str | None = None
    synthetic: bool = False
    source_hashes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.values.shape != self.grid.shape or self.nodata.shape != self.grid.shape:
            raise RasterError("values/nodata shape does not match the grid")
        if self.water is not None and self.water.shape != self.grid.shape:
            raise RasterError("water mask shape does not match the grid")
        if np.any(np.isfinite(self.values) & self.nodata):
            raise RasterError("nodata cells must hold NaN, not numbers")

    @property
    def body(self) -> Body:
        return self.grid.body

    def crop(self, row0: int, col0: int, height: int, width: int) -> SourceRaster:
        """Sub-raster (the grid is cropped consistently)."""
        sub = self.grid.window(row0, col0, height, width)
        rows, cols = slice(row0, row0 + height), slice(col0, col0 + width)
        return SourceRaster(
            grid=sub,
            values=self.values[rows, cols].copy(),
            nodata=self.nodata[rows, cols].copy(),
            native_resolution_m=self.native_resolution_m,
            support_scale_m=self.support_scale_m,
            vertical_reference=self.vertical_reference,
            water=None if self.water is None else self.water[rows, cols].copy(),
            product_id=self.product_id,
            synthetic=self.synthetic,
            source_hashes=self.source_hashes,
        )


def projected_posting_m(
    crs: CRS, gt: tuple[float, float, float, float, float, float], height: int, width: int,
) -> float:
    """Projected pixel spacing in physical metres; resolve materially distorted map units geodesically."""
    ux, uy = (float(axis.unit_conversion_factor) for axis in crs.axis_info[:2])
    nominal = max(math.hypot(gt[1] * ux, gt[4] * uy), math.hypot(gt[2] * ux, gt[5] * uy))
    rr, cc = np.meshgrid(np.linspace(.5, height - .5, 5), np.linspace(.5, width - .5, 5))
    xx, yy = gt[0] + cc * gt[1] + rr * gt[2], gt[3] + cc * gt[4] + rr * gt[5]
    inverse = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    lon, lat = inverse.transform(xx, yy)
    geod = crs.get_geod()
    if geod is None:
        raise RasterError("Projected source has no resolved body geometry", code="UNSUPPORTED_CRS")
    spacings = []
    for dx, dy in ((gt[1], gt[4]), (gt[2], gt[5])):
        lon2, lat2 = inverse.transform(xx + dx, yy + dy)
        _, _, distance = geod.inv(lon, lat, lon2, lat2)
        spacings.append(float(np.max(distance)))
    physical = max(spacings)
    if not math.isfinite(physical) or physical <= 0:
        raise RasterError("Projected source ground spacing is unresolved", code="UNSUPPORTED_CRS")
    # Preserve declared map spacing when its discrepancy is within the baseline
    # projection policy. Material distortion must never change native support
    # between ingestion evidence and subsequent metric normalization.
    return nominal if nominal > 0 and abs(physical / nominal - 1) <= .01 else physical


def native_cell_size_m(raw: RawRaster, body: Body) -> float:
    """Conservative native pixel-axis spacing in metres over the source footprint."""
    a, b, d, e = raw.geotransform[1], raw.geotransform[2], raw.geotransform[4], raw.geotransform[5]
    if raw.crs_wkt is None:
        raise RasterError("raster has no CRS", code="UNSUPPORTED_CRS")
    crs = CRS.from_wkt(raw.crs_wkt)
    if crs.is_projected:
        return projected_posting_m(crs, raw.geotransform, *raw.values.shape)
    height, width = raw.values.shape
    x0, y0 = raw.geotransform[0], raw.geotransform[3]
    rr, cc = np.meshgrid(np.linspace(.5, height - .5, 5), np.linspace(.5, width - .5, 5))
    lon_c, lat_c = x0 + cc * a + rr * b, y0 + cc * d + rr * e
    geod = body_geometry(body).geod()
    _, _, dx = geod.inv(lon_c, lat_c, lon_c + a, lat_c + d)
    _, _, dy = geod.inv(lon_c, lat_c, lon_c + b, lat_c + e)
    return float(max(np.max(dx), np.max(dy)))


def resample_to_grid(
    raw: RawRaster,
    values_m: FloatArray,
    missing: BoolArray,
    dst: AnalysisGridSpec,
    *,
    src_cell_size_m: float,
    min_valid_fraction: float = 1.0,
) -> tuple[FloatArray, BoolArray]:
    """Area-average already-normalised metres onto ``dst``; refuses to upsample.

    ``values_m``/``missing`` come from :func:`normalize_elevation` on ``raw`` (same shape).  A destination cell is
    valid when at least ``min_valid_fraction`` of its footprint is covered by valid source cells.
    """
    if raw.crs_wkt is None:
        raise RasterError("raster has no CRS", code="UNSUPPORTED_CRS")
    if values_m.shape != raw.values.shape or missing.shape != values_m.shape:
        raise RasterError("values/missing shape does not match the raw raster")
    if dst.cell_size_m < src_cell_size_m * (1.0 - 1e-6):
        raise ScaleError(
            f"destination cell {dst.cell_size_m} m is finer than the source {src_cell_size_m:.3f} m; upsampling refused"
        )
    if not 0.0 < min_valid_fraction <= 1.0:
        raise RasterError("min_valid_fraction must be in (0, 1]")
    src_transform = Affine(
        raw.geotransform[1],
        raw.geotransform[2],
        raw.geotransform[0],
        raw.geotransform[4],
        raw.geotransform[5],
        raw.geotransform[3],
    )
    dst_transform = Affine(dst.cell_size_m, 0.0, dst.origin_x_m, 0.0, -dst.cell_size_m, dst.origin_y_m)
    ok = ~missing
    weighted = np.zeros(dst.shape, dtype=np.float64)
    coverage = np.zeros(dst.shape, dtype=np.float64)
    reproject(
        source=np.where(ok, values_m, 0.0).astype(np.float64),
        destination=weighted,
        src_transform=src_transform,
        src_crs=raw.crs_wkt,
        dst_transform=dst_transform,
        dst_crs=dst.crs_wkt,
        resampling=Resampling.average,
        init_dest_nodata=False,
    )
    reproject(
        source=ok.astype(np.float64),
        destination=coverage,
        src_transform=src_transform,
        src_crs=raw.crs_wkt,
        dst_transform=dst_transform,
        dst_crs=dst.crs_wkt,
        resampling=Resampling.average,
        init_dest_nodata=False,
    )
    valid = coverage >= min_valid_fraction - 1e-9
    valid &= coverage > 0.0
    out = np.full(dst.shape, np.nan)
    np.divide(weighted, coverage, out=out, where=valid)
    return out, np.asarray(valid, dtype=bool)


def coarsen_metric_grid(
    grid: AnalysisGridSpec, values: FloatArray, missing: BoolArray, support_m: float,
) -> tuple[AnalysisGridSpec, FloatArray, BoolArray]:
    """Area-average a metric grid at arbitrary coarser support, retaining only complete footprints.

    The NW origin is fixed. Partial cells on the south/east boundary are omitted;
    any missing contributor invalidates its destination cell. No interpolation of
    categorical data or improvement of source resolution is permitted here.
    """
    if not math.isfinite(support_m) or support_m < grid.cell_size_m - 1e-9:
        raise ScaleError("Requested support is finer than the available metric grid")
    cols = int(math.floor(grid.width * grid.cell_size_m / support_m + 1e-9))
    rows = int(math.floor(grid.height * grid.cell_size_m / support_m + 1e-9))
    if min(rows, cols) < 1:
        raise ScaleError("Source extent is smaller than one cell at requested support")
    dst = AnalysisGridSpec(grid.body, grid.crs_wkt, grid.origin_x_m, grid.origin_y_m, support_m, cols, rows)
    raw = RawRaster(values, grid.geotransform, grid.crs_wkt, None, str(values.dtype), "MEM", 1, 0)
    mean, valid = resample_to_grid(raw, values, missing, dst, src_cell_size_m=grid.cell_size_m)
    return dst, mean, valid
