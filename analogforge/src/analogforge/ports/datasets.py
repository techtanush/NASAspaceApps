"""FROZEN CONTRACT KIT FILE - analogforge.ports.datasets

The drop-in dataset manifest: the "last Lego piece" slot (architecture 36 / 37).
Any raster product (NASA-provided at the hackathon, or a synthetic practice raster) is
described by one ``manifest.yaml`` beside its files in ``analogforge/data/incoming/<dataset_id>/``.
The manifest is validated against this model (and contracts/dataset-manifest.schema.json,
which is generated from it). DO NOT EDIT in any branch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from analogforge.ports.common import Body, PortModel

DATASET_MANIFEST_VERSION = "1.0"

DatasetRole = Literal[
    "TARGET_TERRAIN",  # Moon/Mars elevation used to characterize the planetary target
    "EARTH_TERRAIN",  # Earth elevation used for candidate screening, analysis and routes
    "EARTH_MINERAL",  # Earth mineral-context product (EMIT-like); categorical
    "LUNAR_THERMAL",  # Moon thermal product (Diviner-like); kelvin
    "CONTEXT_ONLY",  # displayable context; never evidence for a qualification
]
DatasetFormat = Literal[
    "GEOTIFF", "COG", "HGT", "HGT_ZIP", "PDS4_IMG", "PDS3_IMG", "NETCDF", "HDF5", "ASCII_GRID", "OTHER"
]
DatasetQuantity = Literal[
    "ELEVATION", "RADIUS", "SLOPE_DEG", "MINERAL_CLASS", "BAND_DEPTH", "TEMPERATURE_K", "OTHER"
]
DatasetUnit = Literal["m", "km", "deg", "K", "class", "dimensionless"]


class DatasetFile(PortModel):
    path: str = Field(min_length=1)  # relative to the dataset directory; no '..', no absolute path
    role: Literal["DATA", "LABEL", "METADATA", "MASK", "DOCUMENTATION"] = "DATA"
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")  # filled/verified by validate
    media_type: str | None = None

    @model_validator(mode="after")
    def _relative(self) -> DatasetFile:
        if self.path.startswith(("/", "\\")) or ".." in self.path.replace("\\", "/").split("/"):
            raise ValueError("dataset file paths must be relative and stay inside the dataset dir")
        return self


class CrsSpec(PortModel):
    epsg: int | None = None  # Earth only (e.g. 4326, 32612)
    wkt: str | None = None  # required for Moon/Mars (IAU/ESRI planetary WKT)

    @model_validator(mode="after")
    def _one(self) -> CrsSpec:
        if (self.epsg is None) == (self.wkt is None):
            raise ValueError("CrsSpec needs exactly one of epsg or wkt")
        return self


class ProductIdentity(PortModel):
    product_id: str | None = None  # e.g. NASADEM_HGT, urn:nasa:pds:... LIDVID
    version: str | None = None
    granule_ids: list[str] = Field(default_factory=list)
    doi: str | None = None
    source_url: str | None = None  # stable landing/source URL; never a signed URL or token


class Acquisition(PortModel):
    start: str | None = None  # ISO 8601
    end: str | None = None
    description: str | None = None  # e.g. "multi-year cumulative", "local time 13:00"


class DatasetManifest(PortModel):
    manifest_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    title: str = Field(min_length=1)
    provider: str = Field(min_length=1)  # e.g. "NASA LP DAAC", "NASA PDS Geosciences", "SYNTHETIC_PRACTICE"
    is_synthetic: bool
    body: Body
    role: DatasetRole
    format: DatasetFormat
    files: list[DatasetFile] = Field(min_length=1)
    primary_file: str
    band: int = Field(default=1, ge=1)
    variable: str | None = None  # NetCDF/HDF variable path when applicable
    quantity: DatasetQuantity
    units: DatasetUnit
    scale_factor: float = 1.0
    offset: float = 0.0
    scale_already_applied: bool = False  # True if the reader (e.g. GDAL) already applies scale/offset
    nodata_value: float | None = None
    reference_radius_m: float | None = Field(default=None, gt=0)  # required when quantity == RADIUS
    vertical_reference: str = Field(min_length=1)
    crs: CrsSpec
    longitude_convention: Literal["NEG180_180", "ZERO_360", "PROJECTED"]
    longitude_direction: Literal["POSITIVE_EAST", "POSITIVE_WEST"] = "POSITIVE_EAST"
    latitude_type: Literal["PLANETOCENTRIC", "PLANETOGRAPHIC", "GEODETIC"]
    pixel_registration: Literal["CENTER", "CORNER", "UNKNOWN"] = "UNKNOWN"
    declared_native_resolution_m: float | None = Field(default=None, gt=0)
    acquisition: Acquisition | None = None
    product_identity: ProductIdentity = Field(default_factory=ProductIdentity)
    license_note: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _semantics(self) -> DatasetManifest:
        if self.primary_file not in {f.path for f in self.files}:
            raise ValueError("primary_file must be one of files[].path")
        if self.is_synthetic != self.provider.upper().startswith("SYNTHETIC"):
            raise ValueError("is_synthetic must be true exactly when provider starts with SYNTHETIC")
        if self.body != "EARTH" and self.crs.wkt is None:
            raise ValueError("Moon/Mars datasets require a planetary WKT CRS (no Earth EPSG)")
        if self.quantity == "RADIUS" and self.reference_radius_m is None:
            raise ValueError("quantity RADIUS requires reference_radius_m")
        if self.role in ("EARTH_TERRAIN", "EARTH_MINERAL") and self.body != "EARTH":
            raise ValueError(f"role {self.role} requires body EARTH")
        if self.role in ("TARGET_TERRAIN", "LUNAR_THERMAL") and self.body == "EARTH":
            raise ValueError(f"role {self.role} requires body MOON or MARS")
        if self.role == "LUNAR_THERMAL" and self.body != "MOON":
            raise ValueError("LUNAR_THERMAL requires body MOON")
        return self


__all__ = [
    "DATASET_MANIFEST_VERSION",
    "Acquisition",
    "CrsSpec",
    "DatasetFile",
    "DatasetFormat",
    "DatasetManifest",
    "DatasetQuantity",
    "DatasetRole",
    "DatasetUnit",
    "ProductIdentity",
]
