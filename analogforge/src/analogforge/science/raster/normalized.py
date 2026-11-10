"""Immutable, deterministic normalized source rasters for authorized evidence reuse.

This private NORMALIZED_RASTER container preserves the validated manifest, original
byte hashes, physical values, georeference and masks. It is distinct from a derived
ANALYSIS_GRID: no derivative or solver state is inferred from it.
"""

import io
import zipfile
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.hashing import canonical_json_bytes
from analogforge.science.datasets.ingest import NormalizedRaster
from analogforge.science.errors import RasterError
from analogforge.science.geometry import BBox
from analogforge.science.hashing_utils import array_sha256
from analogforge.science.raster.source import BoolArray

MEDIA_TYPE = "application/x-npz"
MAX_BYTES = 512 * 1024 * 1024
MEMBERS = ("meta.json", "missing.npy", "values.npy", "water.npy")


class SourceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    format: Literal["analogforge-normalized-source-v1"] = "analogforge-normalized-source-v1"
    manifest: DatasetManifest
    file_hashes: dict[str, str]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    geotransform: tuple[float, float, float, float, float, float]
    crs_wkt: str
    native_resolution_m: float = Field(gt=0)
    bbox_lonlat: BBox
    source_driver: str
    has_water_mask: bool


@dataclass(frozen=True)
class NormalizedSource:
    meta: SourceMeta
    raster: NormalizedRaster
    water: BoolArray | None


def encode_source(
    raster: NormalizedRaster, manifest: DatasetManifest, file_hashes: dict[str, str], bbox: BBox,
    water: BoolArray | None = None,
) -> bytes:
    if raster.crs_wkt is None or raster.native_resolution_m is None:
        raise RasterError("Normalized source requires a CRS and physical native support")
    height, width = raster.values.shape
    meta = SourceMeta(
        manifest=manifest, file_hashes=file_hashes, width=width, height=height,
        geotransform=raster.geotransform, crs_wkt=raster.crs_wkt,
        native_resolution_m=raster.native_resolution_m, source_driver=raster.source_driver,
        has_water_mask=water is not None, bbox_lonlat=bbox,
    )
    arrays = {
        "values.npy": np.asarray(raster.values, dtype="<f8"),
        "missing.npy": np.asarray(raster.missing, dtype=bool),
        "water.npy": np.zeros((height, width), dtype=bool) if water is None else np.asarray(water, dtype=bool),
    }
    if any(a.shape != (height, width) for a in arrays.values()):
        raise RasterError("Normalized source masks must match the source grid")
    if sum(a.nbytes for a in arrays.values()) > MAX_BYTES:
        raise RasterError("Normalized source exceeds the byte budget", code="RESOURCE_LIMIT")
    parts = {"meta.json": canonical_json_bytes(meta.model_dump(mode="json"))}
    for name, array in arrays.items():
        stream = io.BytesIO()
        np.lib.format.write_array(stream, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False)
        parts[name] = stream.getvalue()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in MEMBERS:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o600 << 16
            archive.writestr(info, parts[name])
    return stream.getvalue()


def decode_source(data: bytes) -> NormalizedSource:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if sorted(i.filename for i in infos) != sorted(MEMBERS):
                raise RasterError("Normalized source has missing, duplicate or unexpected members")
            if any(i.compress_type != zipfile.ZIP_STORED or i.flag_bits & 1 for i in infos):
                raise RasterError("Normalized source members must be stored and unencrypted")
            if sum(i.file_size for i in infos) > MAX_BYTES or archive.getinfo("meta.json").file_size > 128 * 1024:
                raise RasterError("Normalized source exceeds the byte budget", code="RESOURCE_LIMIT")
            meta = SourceMeta.model_validate_json(archive.read("meta.json"))
            shape = (meta.height, meta.width)
            arrays: dict[str, NDArray[np.generic]] = {}
            for name in MEMBERS[1:]:
                raw = archive.read(name)
                stream = io.BytesIO(raw)
                if np.lib.format.read_magic(stream) != (1, 0):
                    raise RasterError("Unsupported normalized array format")
                header_shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
                expected = np.dtype("<f8" if name == "values.npy" else bool)
                size = meta.height * meta.width * expected.itemsize
                if header_shape != shape or fortran or dtype != expected or stream.tell() + size != len(raw):
                    raise RasterError("Normalized array shape, type or byte count is invalid")
                arrays[name] = np.frombuffer(raw, dtype=expected, offset=stream.tell()).reshape(shape).copy()
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, ValidationError) as exc:
        raise RasterError("Normalized source container is invalid", code="SOURCE_CONTENT_INVALID") from exc
    values = np.asarray(arrays["values.npy"], dtype=np.float64)
    missing = np.asarray(arrays["missing.npy"], dtype=bool)
    water = np.asarray(arrays["water.npy"], dtype=bool)
    if not np.all(np.isfinite(values[~missing])):
        raise RasterError("Normalized source contains non-finite usable values")
    raster = NormalizedRaster(
        values=values, missing=missing, geotransform=meta.geotransform, crs_wkt=meta.crs_wkt,
        native_resolution_m=meta.native_resolution_m, vertical_reference=meta.manifest.vertical_reference,
        source_driver=meta.source_driver, values_sha256=array_sha256(values),
    )
    return NormalizedSource(meta, raster, water if meta.has_water_mask else None)
