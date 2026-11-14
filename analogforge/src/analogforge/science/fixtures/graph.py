"""In-memory fixture loaders: ``SourceSelector(kind="SYNTHETIC_FIXTURE")`` without touching the file system.

The loaders pass the *stored* (file) arrays of the practice generators through the same
:func:`science.raster.normalize.normalize_elevation` step a ``LOCAL_DATASET`` read uses, so a fixture and the same
dataset read from disk give bit-identical rasters (parity test PARITY-01).  Everything is SYNTHETIC: product ids start
with ``SYNTHETIC_`` and ``SourceRaster.synthetic`` is true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from analogforge.ports import catalog
from analogforge.ports.common import Body
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.science_payloads import GraphSpec
from analogforge.science.fixtures import practice
from analogforge.science.fixtures.practice import PracticeOptions, PracticeProduct
from analogforge.science.geometry import AnalysisGridSpec
from analogforge.science.raster.normalize import normalize_elevation
from analogforge.science.raster.source import SourceRaster

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

RASTER_FIXTURE_IDS: Final = practice.ALL_DATASET_IDS
FIXTURE_IDS: Final = (*RASTER_FIXTURE_IDS, catalog.FIXTURE_CANONICAL_GRAPH)


class UnknownFixtureError(KeyError):
    """The fixture id is not a synthetic fixture of this build."""


@dataclass(frozen=True)
class FixtureArrays:
    """A fixture raster in physical units on its grid (``values`` is NaN where missing)."""

    fixture_id: str
    manifest: DatasetManifest
    grid: AnalysisGridSpec
    values: FloatArray  # metres (ELEVATION/RADIUS->height), kelvin, or class ids (float) per manifest.quantity
    missing: BoolArray
    water: BoolArray | None
    native_resolution_m: float

    @property
    def body(self) -> Body:
        return self.manifest.body

    @property
    def product_id(self) -> str:
        assert self.manifest.product_identity.product_id is not None
        return self.manifest.product_identity.product_id


def _grid_of(product: PracticeProduct) -> AnalysisGridSpec:
    r = product.primary
    crs_wkt = r.wkt
    if crs_wkt is None:
        from pyproj import CRS

        assert r.epsg is not None
        crs_wkt = CRS.from_epsg(r.epsg).to_wkt()
    h, w = r.array.shape
    return AnalysisGridSpec(
        body=product.manifest.body,
        crs_wkt=crs_wkt,
        origin_x_m=r.origin_x_m,
        origin_y_m=r.origin_y_m,
        cell_size_m=r.cell_size_m,
        width=w,
        height=h,
    )


def physical_values(manifest: DatasetManifest, raw: NDArray[np.number]) -> tuple[FloatArray, BoolArray]:
    """Raw stored values to physical values exactly as the dataset path does (scale/offset once, nodata on raw)."""
    if manifest.quantity in ("ELEVATION", "RADIUS"):
        assert manifest.units in ("m", "km")
        values, missing, _ = normalize_elevation(
            raw,
            quantity=manifest.quantity,
            units=manifest.units,
            scale_factor=manifest.scale_factor,
            offset=manifest.offset,
            scale_already_applied=manifest.scale_already_applied,
            reference_radius_m=manifest.reference_radius_m,
            nodata_value=manifest.nodata_value,
        )
        return values, missing
    as_float = raw.astype(np.float64)
    missing = np.zeros(raw.shape, dtype=bool) if manifest.nodata_value is None else raw == manifest.nodata_value
    return np.where(missing, np.nan, as_float * manifest.scale_factor + manifest.offset), np.asarray(
        missing, dtype=bool
    )


def load_fixture_arrays(fixture_id: str, options: PracticeOptions | None = None) -> FixtureArrays:
    """Arrays + geometry of a synthetic raster fixture (what science operations call for ``SYNTHETIC_FIXTURE``)."""
    if fixture_id not in RASTER_FIXTURE_IDS:
        raise UnknownFixtureError(fixture_id)
    product = practice.build_product(fixture_id, options)
    values, missing = physical_values(product.manifest, product.primary.array)
    water: BoolArray | None = None
    for raster in product.rasters:
        if raster.role == "MASK":
            water = np.asarray(raster.array == 1, dtype=bool)
    return FixtureArrays(
        fixture_id=fixture_id,
        manifest=product.manifest,
        grid=_grid_of(product),
        values=values,
        missing=missing,
        water=water,
        native_resolution_m=product.primary.cell_size_m,
    )


def load_source_raster(fixture_id: str, options: PracticeOptions | None = None) -> SourceRaster:
    """The fixture as the canonical :class:`SourceRaster` (elevation/height in metres; terrain fixtures only)."""
    arrays = load_fixture_arrays(fixture_id, options)
    if arrays.manifest.quantity not in ("ELEVATION", "RADIUS"):
        raise UnknownFixtureError(f"{fixture_id} is not a terrain fixture")
    return SourceRaster(
        grid=arrays.grid,
        values=arrays.values,
        nodata=arrays.missing,
        native_resolution_m=arrays.native_resolution_m,
        support_scale_m=arrays.native_resolution_m,
        vertical_reference=arrays.manifest.vertical_reference,
        water=arrays.water,
        product_id=arrays.product_id,
        synthetic=True,
    )


def load_canonical_graph(drop_edges: tuple[tuple[str, str], ...] = ()) -> GraphSpec:
    """The abstract ``canonical-graph-v1`` (mock energies; usable only in ``synthetic`` mode)."""
    from analogforge.science.routing.fixture_graph import canonical_graph_spec

    return canonical_graph_spec(drop_edges)
