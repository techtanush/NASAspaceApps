"""Format-faithful synthetic products and a mocked HTTP world for the adapter replay tests.

Nothing here contacts a network. Files follow the layouts documented for NASADEM .hgt (big-endian int16),
PDS3 detached labels + raw images, PDS4 XML + raw arrays, EMIT-style NetCDF (HDF5) and GeoTIFF; they are
generated from numpy arrays so tests can compare decoder output with an independent expectation.
"""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5netcdf
import httpx
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.transform import from_origin

HGT_VOID = -32768


# ----------------------------------------------------------------------------- NASADEM
def global_heights(rows: int, cols: int, seed: int = 7) -> NDArray[np.int16]:
    rng = np.random.default_rng(seed)
    r, c = np.mgrid[0:rows, 0:cols]
    return (200 + 3 * r + 5 * c + rng.integers(0, 60, size=(rows, cols))).astype(np.int16)


def hgt_bytes(arr: NDArray[np.int16]) -> bytes:
    return arr.astype(">i2").tobytes()


def nasadem_zip(
    path: Path, name: str, heights: NDArray[np.int16], *, num: bool = True, water: NDArray[np.bool_] | None = None
) -> Path:
    n = heights.shape[0]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{name}.hgt", hgt_bytes(heights))
        if num:
            zf.writestr(f"{name}.num", (np.arange(n * n) % 7).astype(np.uint8).tobytes())
        if water is not None:
            zf.writestr(f"{name}.swb", water.astype(np.uint8).tobytes())
    return path


# ----------------------------------------------------------------------------- archives
def zip_with_members(path: Path, members: dict[str, bytes], *, compress: int = zipfile.ZIP_DEFLATED) -> Path:
    with zipfile.ZipFile(path, "w", compress) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def zip_with_symlink(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("n00e000.hgt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "/etc/passwd")
    return path


# ----------------------------------------------------------------------------- PDS3 / PDS4
def pds3_label(
    *,
    data_name: str,
    lines: int,
    samples: int,
    sample_type: str = "MSB_INTEGER",
    bits: int = 16,
    scale: float | None = 1.0,
    offset: float | None = 0.0,
    missing: int | None = None,
    target: str = "MARS",
    unit: str | None = "METER",
    a_radius_km: float | None = 3396.0,
    west: float | None = 0.0,
    east: float | None = 4.0,
    south: float | None = 0.0,
    north: float | None = 4.0,
    resolution: float | None = 1.0,
    direction: str = "EAST",
    product_id: str = "SYN-PRODUCT",
) -> str:
    img = [
        f"  LINES = {lines}",
        f"  LINE_SAMPLES = {samples}",
        f"  SAMPLE_TYPE = {sample_type}",
        f"  SAMPLE_BITS = {bits}",
    ]
    if scale is not None:
        img.append(f"  SCALING_FACTOR = {scale}")
    if offset is not None:
        img.append(f"  OFFSET = {offset} <METERS>")
    if missing is not None:
        img.append(f"  MISSING_CONSTANT = {missing}")
    if unit is not None:
        img.append(f"  UNIT = {unit}")
    proj = []
    if a_radius_km is not None:
        proj.append(f"  A_AXIS_RADIUS = {a_radius_km} <KM>")
    if resolution is not None:
        proj.append(f"  MAP_RESOLUTION = {resolution} <PIXEL/DEGREE>")
    for key, val in (
        ("MAXIMUM_LATITUDE", north),
        ("MINIMUM_LATITUDE", south),
        ("WESTERNMOST_LONGITUDE", west),
        ("EASTERNMOST_LONGITUDE", east),
    ):
        if val is not None:
            proj.append(f"  {key} = {val}")
    proj.append(f"  POSITIVE_LONGITUDE_DIRECTION = {direction}")
    return "\n".join(
        [
            "PDS_VERSION_ID = PDS3",
            "RECORD_TYPE = FIXED_LENGTH",
            f"RECORD_BYTES = {samples * bits // 8}",
            f'^IMAGE = "{data_name}"',
            f"TARGET_NAME = {target}",
            f'PRODUCT_ID = "{product_id}"',
            "OBJECT = IMAGE",
            *img,
            "END_OBJECT = IMAGE",
            "OBJECT = IMAGE_MAP_PROJECTION",
            *proj,
            "END_OBJECT = IMAGE_MAP_PROJECTION",
            "END",
            "",
        ]
    )


def write_pds3(directory: Path, stem: str, raw: NDArray[Any], dtype: str, **label_kwargs: Any) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.img").write_bytes(raw.astype(dtype).tobytes())
    lines, samples = raw.shape
    label_kwargs.setdefault("data_name", f"{stem}.img")
    bits = int(np.dtype(dtype).itemsize * 8)
    label = pds3_label(lines=lines, samples=samples, bits=bits, **label_kwargs)
    lbl = directory / f"{stem}.lbl"
    lbl.write_text(label, encoding="ascii")
    return lbl


def write_pds4(
    directory: Path,
    stem: str,
    raw: NDArray[Any],
    dtype: str,
    *,
    data_type: str = "SignedMSB2",
    scale: float = 1.0,
    offset: float = 0.0,
    missing: float | None = None,
    target: str = "Mars",
    a_radius_km: float = 3396.0,
    unit: str = "m",
    west: float = 0.0,
    east: float = 4.0,
    south: float = 0.0,
    north: float = 4.0,
    doctype: str = "",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.img").write_bytes(raw.astype(dtype).tobytes())
    lines, samples = raw.shape
    special = (
        f"<Special_Constants><missing_constant>{missing}</missing_constant></Special_Constants>"
        if missing is not None
        else ""
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
{doctype}<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
 <Identification_Area><logical_identifier>urn:nasa:pds:syn:data:{stem}</logical_identifier>
  <version_id>1.0</version_id></Identification_Area>
 <Observation_Area><Target_Identification><name>{target}</name></Target_Identification></Observation_Area>
 <File_Area_Observational><File><file_name>{stem}.img</file_name></File>
  <Array_2D_Image><offset unit="byte">0</offset><axes>2</axes><axis_index_order>Last Index Fastest</axis_index_order>
   <Element_Array><data_type>{data_type}</data_type><unit>{unit}</unit><scaling_factor>{scale}</scaling_factor>
    <value_offset>{offset}</value_offset></Element_Array>
   <Axis_Array><axis_name>Line</axis_name><elements>{lines}</elements><sequence_number>1</sequence_number></Axis_Array>
   <Axis_Array><axis_name>Sample</axis_name><elements>{samples}</elements><sequence_number>2</sequence_number></Axis_Array>
   {special}
  </Array_2D_Image></File_Area_Observational>
 <Context_Area><Cartography><Spatial_Domain><Bounding_Coordinates>
  <west_bounding_coordinate>{west}</west_bounding_coordinate><east_bounding_coordinate>{east}</east_bounding_coordinate>
  <north_bounding_coordinate>{north}</north_bounding_coordinate><south_bounding_coordinate>{south}</south_bounding_coordinate>
  </Bounding_Coordinates></Spatial_Domain>
  <Geodetic_Model><latitude_type>Planetocentric</latitude_type><a_axis_radius unit="km">{a_radius_km}</a_axis_radius>
   <longitude_direction>Positive East</longitude_direction></Geodetic_Model></Cartography></Context_Area>
</Product_Observational>
"""
    path = directory / f"{stem}.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def pds_index(rows: Iterable[tuple[str, float, float, float, float]]) -> tuple[str, str]:
    """Return (label_text, table_text) for a fixed-width PDS3 INDEX_TABLE."""
    rows = list(rows)
    widths = {
        "FILE_SPECIFICATION_NAME": 32,
        "MINIMUM_LATITUDE": 9,
        "MAXIMUM_LATITUDE": 9,
        "WESTERNMOST_LONGITUDE": 9,
        "EASTERNMOST_LONGITUDE": 9,
    }
    lines = []
    for name, south, north, west, east in rows:
        lines.append(f'"{name}"'.ljust(32) + "".join(f"{v:9.3f}" for v in (south, north, west, east)))
    row_bytes = sum(widths.values())
    cols = []
    start = 1
    for col, width in widths.items():
        cols.append(
            f"  OBJECT = COLUMN\n    NAME = {col}\n    START_BYTE = {start}\n    BYTES = {width}\n  END_OBJECT = COLUMN"
        )
        start += width
    label = (
        f'PDS_VERSION_ID = PDS3\n^INDEX_TABLE = "INDEX.TAB"\nOBJECT = INDEX_TABLE\n  ROWS = {len(rows)}\n'
        f"  ROW_BYTES = {row_bytes}\n" + "\n".join(cols) + "\nEND_OBJECT = INDEX_TABLE\nEND\n"
    )
    return label, "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- EMIT-style NetCDF
def write_emit_nc(
    path: Path,
    ids: NDArray[np.int16],
    *,
    fill: int = -9999,
    mask: NDArray[np.uint8] | None = None,
    names: dict[int, str] | None = None,
    lat: NDArray[np.float64] | None = None,
    lon: NDArray[np.float64] | None = None,
    prefix: str = "group_1",
) -> Path:
    rows, cols = ids.shape
    with h5netcdf.File(str(path), "w") as f:
        f.dimensions = {"downtrack": rows, "crosstrack": cols}
        v = f.create_variable(f"{prefix}_mineral_id", ("downtrack", "crosstrack"), "i2", fillvalue=fill)
        v[:] = ids
        bd = f.create_variable(f"{prefix}_band_depth", ("downtrack", "crosstrack"), "f4", fillvalue=-9999.0)
        bd[:] = np.where(ids == fill, -9999.0, 0.05 + 0.01 * (ids % 5)).astype(np.float32)
        if mask is not None:
            m = f.create_variable("mask", ("downtrack", "crosstrack"), "u1")
            m[:] = mask
        if lat is not None and lon is not None:
            loc = f.create_group("location")
            la = loc.create_variable("lat", ("downtrack", "crosstrack"), "f8")
            la[:] = lat
            lo = loc.create_variable("lon", ("downtrack", "crosstrack"), "f8")
            lo[:] = lon
        if names is not None:
            md = f.create_group("mineral_metadata")
            md.dimensions = {"n": len(names)}
            idx = md.create_variable("index", ("n",), "i2")
            idx[:] = np.array(list(names), dtype=np.int16)
            nm = md.create_variable("name", ("n",), "S16")
            nm[:] = np.array([v.encode() for v in names.values()], dtype="S16")
        f.attrs["title"] = "SYNTHETIC EMIT-style L2B MIN"
    return path


# ----------------------------------------------------------------------------- GeoTIFF
def write_geotiff(
    path: Path,
    arr: NDArray[np.float32],
    *,
    crs: str | None = "EPSG:32612",
    pixel: float = 10.0,
    west: float = 500000.0,
    north: float = 3900000.0,
    nodata: float | None = -9999.0,
) -> Path:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=from_origin(west, north, pixel, pixel),
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
    return path


# ----------------------------------------------------------------------------- mocked HTTP world
Handler = Callable[[httpx.Request], httpx.Response]


@dataclass
class Call:
    host: str
    path: str
    url: str
    headers: dict[str, str]


@dataclass
class World:
    """Routes ``(host, path) -> handler`` and records every request. Unknown routes answer 404."""

    routes: dict[tuple[str, str], Handler] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            Call(
                request.url.host, request.url.path, str(request.url), {k.lower(): v for k, v in request.headers.items()}
            )
        )
        handler = self.routes.get((request.url.host, request.url.path))
        if handler is None:
            return httpx.Response(404, text="not found")
        return handler(request)

    def client(self, bearer: str | None = "TEST-TOKEN") -> httpx.Client:
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
        return httpx.Client(transport=httpx.MockTransport(self.handle), headers=headers)

    def hosts_called(self) -> list[str]:
        return [c.host for c in self.calls]

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class GranuleSpec:
    concept_id: str
    granule_ur: str
    box: tuple[float, float, float, float]  # west, south, east, north
    download_url: str
    payload: bytes
    checksum: str | None = None  # hex sha256; None => provider supplies none
    checksum_algorithm: str = "SHA-256"
    declared_size: int | None = None


def umm_item(g: GranuleSpec) -> dict[str, Any]:
    name = g.download_url.split("?")[0].rsplit("/", 1)[-1]
    arch: dict[str, Any] = {
        "Name": name,
        "SizeInBytes": g.declared_size if g.declared_size is not None else len(g.payload),
    }
    if g.checksum is not None:
        arch["Checksum"] = {"Value": g.checksum, "Algorithm": g.checksum_algorithm}
    w, s, e, n = g.box
    return {
        "meta": {"concept-id": g.concept_id},
        "umm": {
            "GranuleUR": g.granule_ur,
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "BoundingRectangles": [
                            {
                                "WestBoundingCoordinate": w,
                                "SouthBoundingCoordinate": s,
                                "EastBoundingCoordinate": e,
                                "NorthBoundingCoordinate": n,
                            }
                        ]
                    }
                }
            },
            "DataGranule": {"ArchiveAndDistributionInformation": [arch]},
            "RelatedUrls": [
                {"URL": g.download_url, "Type": "GET DATA"},
                {"URL": "https://example.invalid/browse.png", "Type": "GET RELATED VISUALIZATION"},
            ],
        },
    }


def install_cmr(
    world: World, granules: list[GranuleSpec], *, reverse_order: bool = True, hits_header: bool = True
) -> None:
    """CMR-style granule search: bounding_box filter, page_size paging via CMR-Search-After, CMR-Hits."""
    by_id = {g.concept_id: g for g in granules}

    def intersects(g: GranuleSpec, box: str) -> bool:
        w, s, e, n = (float(v) for v in box.split(","))
        gw, gs, ge, gn = g.box
        return gw < e and ge > w and gs < n and gn > s

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if "concept_id" in params:
            g = by_id.get(params["concept_id"])
            items = [umm_item(g)] if g else []
            return httpx.Response(200, json={"hits": len(items), "items": items})
        hits = [g for g in granules if intersects(g, params["bounding_box"])]
        hits.sort(key=lambda g: g.granule_ur, reverse=reverse_order)
        size = int(params.get("page_size", "10"))
        start = int(request.headers.get("cmr-search-after", "0"))
        page = hits[start : start + size]
        headers: dict[str, str] = {}
        if hits_header:
            headers["CMR-Hits"] = str(len(hits))
        if start + size < len(hits):
            headers["CMR-Search-After"] = str(start + size)
        return httpx.Response(200, json={"hits": len(hits), "items": [umm_item(g) for g in page]}, headers=headers)

    world.routes[("cmr.earthdata.nasa.gov", "/search/granules.umm_json")] = handler
    for g in granules:
        host_path = g.download_url.split("://", 1)[1].split("?")[0]
        host, _, path = host_path.partition("/")

        def download(request: httpx.Request, payload: bytes = g.payload) -> httpx.Response:
            return httpx.Response(200, content=payload, headers={"content-type": "application/octet-stream"})

        world.routes.setdefault((host, "/" + path), download)


def json_bytes(obj: object) -> bytes:
    return json.dumps(obj).encode()


def bytesio(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)
