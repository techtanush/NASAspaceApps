"""Analytic checks for arbitrary metric support and normalized geographic sources."""

import numpy as np
import pytest
from pyproj import CRS

from analogforge.science.datasets.ingest import NormalizedRaster
from analogforge.science.errors import ScaleError
from analogforge.science.geometry import AnalysisGridSpec
from analogforge.science.ops.terrain import prepare
from analogforge.science.raster.project import physical_support
from analogforge.science.raster.source import SourceRaster, coarsen_metric_grid


def test_noninteger_area_average_preserves_plane_and_invalidates_missing_contributors() -> None:
    grid = AnalysisGridSpec("EARTH", CRS.from_epsg(32612).to_wkt(), 500000, 4000000, 90, 24, 24)
    # Planar z=x, sampled at source-cell centres. A 450 m cell combines five
    # postings, while 480 m needs fractional boundary weights.
    values = np.broadcast_to((np.arange(24) + .5) * 90, grid.shape).copy()
    missing = np.zeros(grid.shape, dtype=bool)
    dst, mean, valid = coarsen_metric_grid(grid, values, missing, 480)
    assert dst.shape == (4, 4) and valid.all()
    # Exact piecewise-constant area integral of the first 480 m footprint.
    expected = (sum((i + .5) * 90 * 90 for i in range(5)) + 495 * 30) / 480
    assert mean[0, 0] == pytest.approx(expected, abs=1e-8)
    missing[1, 5] = True  # contributes to two adjacent destination cells
    _, _, valid = coarsen_metric_grid(grid, values, missing, 480)
    assert not valid[0, 0] and not valid[0, 1]
    assert valid[-1, -1]
    with pytest.raises(ScaleError):
        coarsen_metric_grid(grid, values, missing, 60)


def test_preparation_uses_actual_grid_support_and_conservative_water_mask() -> None:
    grid = AnalysisGridSpec("EARTH", CRS.from_epsg(32612).to_wkt(), 500000, 4000000, 94, 32, 32)
    values = np.full(grid.shape, 100.0)
    missing = np.zeros(grid.shape, dtype=bool)
    water = np.zeros(grid.shape, dtype=bool)
    water[10, 10] = True
    source = SourceRaster(grid, values, missing, 93.1, 94, "TEST", water=water)
    native = prepare(source, 60, 1e-12)
    assert native.support_m == 94 and native.grid.shape == grid.shape
    coarse = prepare(source, 480, 1e-12)
    assert coarse.support_m == 480 and coarse.water[1, 1]
    assert not coarse.surf.valid[1, 1]
    assert np.allclose(coarse.surf.slope_deg[coarse.surf.valid], 0, atol=1e-8)


def test_projected_foot_units_and_anisotropic_pixels_are_physical_metres() -> None:
    crs = CRS.from_epsg(2227)  # US survey feet
    values = np.ones((10, 10))
    raster = NormalizedRaster(values, np.zeros_like(values, dtype=bool),
                              (0, 100, 0, 0, 0, -200), crs.to_wkt(), 100,
                              "TEST", "MEM", "a" * 64)
    assert physical_support(raster, crs) == pytest.approx(200 * 1200 / 3937, rel=1e-10)
