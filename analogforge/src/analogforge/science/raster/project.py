"""Convert validated source grids to body-specific metric grids without inventing support."""

from collections.abc import Callable

import numpy as np
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

from analogforge.ports.datasets import DatasetManifest
from analogforge.science.datasets.ingest import NormalizedRaster
from analogforge.science.errors import GeometryError, RasterError
from analogforge.science.geometry import (
    DEFAULT_MAX_LINEAR_DISTORTION,
    AnalysisGridSpec,
    BBox,
    LongitudeConvention,
    assert_crs_matches_body,
    bbox_to_projected_bounds,
    projected_frame_for_aoi,
    validate_projection_distortion,
)
from analogforge.science.raster.source import BoolArray, RawRaster, SourceRaster, resample_to_grid

MAX_PROJECTED_CELLS = 64_000_000


def physical_support(raster: NormalizedRaster, crs: CRS, *, ground_distances: bool = False) -> float:
    """Largest native pixel-axis spacing (metres), sampled across geographic latitude."""
    gt = raster.geotransform
    if crs.is_projected and not ground_distances:
        factors = [float(axis.unit_conversion_factor) for axis in crs.axis_info[:2]]
        return float(max(np.hypot(gt[1] * factors[0], gt[4] * factors[1]),
                         np.hypot(gt[2] * factors[0], gt[5] * factors[1])))
    if not crs.is_geographic and not crs.is_projected:
        raise RasterError("Source CRS is neither geographic nor projected", code="UNSUPPORTED_CRS")
    rows, cols = raster.values.shape
    rr, cc = np.meshgrid(np.linspace(0.5, rows - 0.5, 5), np.linspace(0.5, cols - 0.5, 5))
    x = gt[0] + cc * gt[1] + rr * gt[2]
    y = gt[3] + cc * gt[4] + rr * gt[5]
    geod = crs.get_geod()
    if geod is None:
        raise RasterError("Geographic source has no resolved body geometry", code="UNSUPPORTED_CRS")
    sizes = []
    geographic = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True) if crs.is_projected else None
    for dx, dy in ((gt[1], gt[4]), (gt[2], gt[5])):
        if geographic is None:
            lon, lat, lon2, lat2 = x, y, x + dx, np.clip(y + dy, -90, 90)
        else:
            lon, lat = geographic.transform(x, y)
            lon2, lat2 = geographic.transform(x + dx, y + dy)
        _, _, distances = geod.inv(lon, lat, lon2, lat2)
        sizes.append(float(np.max(distances)))
    return max(sizes)


def project_source(
    raster: NormalizedRaster,
    manifest: DatasetManifest,
    bbox: BBox,
    *,
    water: BoolArray | None = None,
    source_hashes: tuple[str, ...] = (),
    product_id: str | None = None,
    check: Callable[[], None],
    max_linear_distortion: float = DEFAULT_MAX_LINEAR_DISTORTION,
) -> SourceRaster:
    if raster.crs_wkt is None:
        raise RasterError("Source CRS is missing", code="UNSUPPORTED_CRS")
    assert_crs_matches_body(manifest.body, raster.crs_wkt)
    crs = CRS.from_wkt(raster.crs_wkt)
    convention: LongitudeConvention = "ZERO_360" if max(bbox[0], bbox[2]) > 180 else "NEG180_180"
    source_frame_valid = True
    if crs.is_projected:
        try:
            validate_projection_distortion(manifest.body, raster.crs_wkt, bbox, convention,
                                           max_linear_distortion=max_linear_distortion)
        except GeometryError as exc:
            if exc.detail_code != "DISTORTION_EXCEEDED":
                raise
            source_frame_valid = False
    gt = raster.geotransform
    height, width = raster.values.shape
    native = float(physical_support(raster, crs, ground_distances=not source_frame_valid))
    if not np.isfinite(native) or native <= 0:
        raise RasterError("Native physical support is unresolved", code="UNSUPPORTED_CRS")
    metric = crs.is_projected and all(abs(axis.unit_conversion_factor - 1) < 1e-12 for axis in crs.axis_info[:2])
    direct = (source_frame_valid and metric and gt[2] == 0 and gt[4] == 0
              and gt[5] < 0 and abs(gt[1] + gt[5]) < 1e-6 * gt[1])
    if direct:
        grid = AnalysisGridSpec(manifest.body, raster.crs_wkt, gt[0], gt[3], gt[1], width, height)
        values = np.where(raster.missing, np.nan, raster.values)
        missing = np.asarray(raster.missing, dtype=bool)
    else:
        frame = projected_frame_for_aoi(manifest.body, bbox, convention,
                                        max_linear_distortion=max_linear_distortion)
        xmin, ymin, xmax, ymax = bbox_to_projected_bounds(frame, bbox, convention)
        cell = float(np.ceil(native))
        x0, y0 = np.floor(xmin / cell) * cell, np.ceil(ymax / cell) * cell
        cols, rows = int(np.ceil((xmax - x0) / cell)), int(np.ceil((y0 - ymin) / cell))
        if rows < 1 or cols < 1 or rows * cols > MAX_PROJECTED_CELLS:
            raise RasterError("Projected raster exceeds the bounded cell budget", code="RESOURCE_LIMIT")
        grid = AnalysisGridSpec(manifest.body, frame.crs_wkt, x0, y0, cell, cols, rows)
        raw = RawRaster(raster.values, gt, raster.crs_wkt, None, str(raster.values.dtype), raster.source_driver, 1, 0)
        check()
        values, valid = resample_to_grid(raw, raster.values, raster.missing, grid, src_cell_size_m=native)
        src_transform = Affine.from_gdal(*gt)
        dst_transform = Affine.from_gdal(*grid.geotransform)
        if manifest.quantity == "MINERAL_CLASS":
            categorical = np.full(grid.shape, np.nan)
            reproject(
                np.where(raster.missing, np.nan, raster.values), categorical,
                src_transform=src_transform, src_crs=raster.crs_wkt,
                dst_transform=dst_transform, dst_crs=grid.crs_wkt,
                src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest,
            )
            values = categorical
        if water is not None:
            projected_water = np.zeros(grid.shape, dtype=np.uint8)
            reproject(
                water.astype(np.uint8), projected_water,
                src_transform=src_transform, src_crs=raster.crs_wkt,
                dst_transform=dst_transform, dst_crs=grid.crs_wkt, resampling=Resampling.max,
            )
            water = projected_water > 0
        # Average resampling clips its footprint to the source. Reject partially
        # outside cells instead of calling their clipped fraction fully covered.
        inverse = Transformer.from_crs(grid.crs_wkt, raster.crs_wkt, always_xy=True)
        affine_inverse = ~src_transform
        col_indices = np.arange(grid.width, dtype=float)
        for start in range(0, grid.height, 128):
            check()
            row_indices = np.arange(start, min(start + 128, grid.height), dtype=float)
            xx, yy = np.meshgrid(col_indices, row_indices)
            inside = np.ones(xx.shape, dtype=bool)
            for dc, dr in ((0., 0.), (1., 0.), (0., 1.), (1., 1.), (.5, .5)):
                sx, sy = inverse.transform(grid.origin_x_m + (xx + dc) * cell,
                                           grid.origin_y_m - (yy + dr) * cell)
                if crs.is_geographic:
                    centre = gt[0] + width * gt[1] / 2
                    sx = sx + 360 * np.round((centre - sx) / 360)
                sc, sr = affine_inverse * (sx, sy)
                inside &= np.isfinite(sc) & np.isfinite(sr) & (sc >= 0) & (sr >= 0) & (sc <= width) & (sr <= height)
            valid[start:start + len(row_indices)] &= inside
        missing = ~valid | ~np.isfinite(values)
        values = np.where(missing, np.nan, values)
    check()
    return SourceRaster(
        grid=grid, values=values, nodata=missing, native_resolution_m=native,
        support_scale_m=max(native, grid.cell_size_m), vertical_reference=manifest.vertical_reference,
        water=water, product_id=product_id, synthetic=manifest.is_synthetic, source_hashes=source_hashes,
    )
