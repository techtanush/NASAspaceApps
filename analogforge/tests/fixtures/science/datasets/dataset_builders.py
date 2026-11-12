"""Tiny format-faithful dataset builders for the dataset-slot tests (SCN-11/13/14).

Each ``build_*`` writes one dataset directory (data files only, no ``manifest.yaml``) under ``root / dataset_id`` and
returns the manifest as a plain dict that validates (``is_synthetic`` datasets, provider ``SYNTHETIC_TEST``).  The
tests then perturb dict or files to make exactly one check fail.  Nothing here depends on ``science.fixtures``.
"""

from __future__ import annotations

import copy
import struct
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin

from analogforge.science.geometry import body_geometry

EARTH_UTM = CRS.from_epsg(32612)
MARS_GEO_WKT = body_geometry("MARS").geographic_crs().to_wkt()
MOON_GEO_WKT = body_geometry("MOON").geographic_crs().to_wkt()
MOON_SOUTH_POLAR_WKT = CRS.from_proj4(
    "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
).to_wkt()
MARS_EQC_WKT = CRS.from_proj4("+proj=eqc +lat_ts=0 +lon_0=0 +R=3396190 +units=m +no_defs").to_wkt()
MOON_EQC_WKT = CRS.from_proj4("+proj=eqc +lat_ts=0 +lon_0=0 +R=1737400 +units=m +no_defs").to_wkt()


def base_manifest(dataset_id: str, **overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "dataset_id": dataset_id,
        "title": f"Synthetic test dataset {dataset_id}",
        "provider": "SYNTHETIC_TEST",
        "is_synthetic": True,
        "pixel_registration": "CENTER",
        "latitude_type": "GEODETIC",
        "longitude_direction": "POSITIVE_EAST",
        "license_note": "SYNTHETIC TEST DATA - not NASA terrain",
        "citation": "AnalogForge test builders (synthetic)",
        "vertical_reference": "synthetic datum",
    }
    manifest.update(overrides)
    return manifest


def ramp(height: int, width: int, base: float = 100.0, step: float = 2.0) -> np.ndarray:
    """Deterministic non-flat surface (varies along both axes)."""
    rows, cols = np.mgrid[0:height, 0:width]
    return base + step * cols + 0.5 * step * rows + (rows * cols % 7)


def _gtiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: Any | None,
    transform: Any,
    nodata: float | None,
    scale: float = 1.0,
    offset: float = 0.0,
) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1, dtype=str(data.dtype),
        crs=crs, transform=transform, nodata=nodata,
    ) as dst:  # fmt: skip
        dst.write(data, 1)
        if scale != 1.0 or offset != 0.0:
            dst.scales = (scale,)
            dst.offsets = (offset,)


def build_geotiff_earth(root: Path, dataset_id: str = "test-earth-dem") -> dict[str, Any]:
    d = root / dataset_id
    d.mkdir(parents=True)
    data = ramp(20, 20).astype("float32")
    data[2, 3] = -32768
    data[10, 10] = -32768
    _gtiff(d / "dem.tif", data, crs=EARTH_UTM, transform=from_origin(500000, 4000000, 30, 30), nodata=-32768)
    return base_manifest(
        dataset_id, body="EARTH", role="EARTH_TERRAIN", format="GEOTIFF",
        files=[{"path": "dem.tif", "role": "DATA"}], primary_file="dem.tif", quantity="ELEVATION", units="m",
        nodata_value=-32768, crs={"epsg": 32612}, longitude_convention="PROJECTED", declared_native_resolution_m=30,
    )  # fmt: skip


def build_geotiff_mars_scaled(root: Path, dataset_id: str = "test-mars-dem") -> dict[str, Any]:
    """int16 GeoTIFF with GDAL scale 0.5 / offset -100 (metres = raw*0.5 - 100), planetary geographic CRS, 0-360."""
    d = root / dataset_id
    d.mkdir(parents=True)
    raw = (np.arange(24 * 24).reshape(24, 24) % 400 + 200).astype("int16")
    raw[0, 0] = -32768
    _gtiff(
        d / "mola.tif", raw, crs=CRS.from_wkt(MARS_GEO_WKT), transform=from_origin(190.0, 10.0, 0.25, 0.25),
        nodata=-32768, scale=0.5, offset=-100.0,
    )  # fmt: skip
    return base_manifest(
        dataset_id, body="MARS", role="TARGET_TERRAIN", format="GEOTIFF",
        files=[{"path": "mola.tif", "role": "DATA"}], primary_file="mola.tif", quantity="ELEVATION", units="m",
        scale_factor=0.5, offset=-100.0, scale_already_applied=True, nodata_value=-32768,
        vertical_reference="Mars areoid (synthetic)", crs={"wkt": MARS_GEO_WKT}, longitude_convention="ZERO_360",
        latitude_type="PLANETOCENTRIC", declared_native_resolution_m=14800,
    )  # fmt: skip


def hgt_tile(path: Path, west_lon: int, south_lat: int, seed: int = 1, void: bool = True) -> np.ndarray:
    rows, cols = np.mgrid[0:1201, 0:1201]
    lon = west_lon + cols / 1200.0
    lat = south_lat + 1 - rows / 1200.0
    # elevation is a function of absolute lon/lat so shared border samples agree between neighbouring tiles
    data = (1000 + 300 * np.sin(lon * 7.0) + 200 * np.cos(lat * 5.0) + seed * 0).astype(">i2")
    if void:
        data[100:104, 100:104] = -32768
    path.write_bytes(data.tobytes())
    return data


def build_hgt_pair(root: Path, dataset_id: str = "test-hgt") -> dict[str, Any]:
    d = root / dataset_id
    d.mkdir(parents=True)
    hgt_tile(d / "N36W112.hgt", -112, 36)
    hgt_tile(d / "N36W111.hgt", -111, 36, void=False)
    return base_manifest(
        dataset_id, body="EARTH", role="EARTH_TERRAIN", format="HGT",
        files=[{"path": "N36W112.hgt", "role": "DATA"}, {"path": "N36W111.hgt", "role": "DATA"}],
        primary_file="N36W112.hgt", quantity="ELEVATION", units="m", nodata_value=-32768,
        vertical_reference="EGM96 geoid (synthetic)", crs={"epsg": 4326}, longitude_convention="NEG180_180",
        declared_native_resolution_m=92,
    )  # fmt: skip


def build_hgt_zip(root: Path, dataset_id: str = "test-hgt-zip") -> dict[str, Any]:
    d = root / dataset_id
    d.mkdir(parents=True)
    tmp = root / f"_{dataset_id}_tmp"
    tmp.mkdir()
    hgt_tile(tmp / "N36W112.hgt", -112, 36)
    with zipfile.ZipFile(d / "N36W112.hgt.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp / "N36W112.hgt", "N36W112.hgt")
    manifest = build_hgt_manifest_for_zip(dataset_id)
    return manifest


def build_hgt_manifest_for_zip(dataset_id: str) -> dict[str, Any]:
    return base_manifest(
        dataset_id, body="EARTH", role="EARTH_TERRAIN", format="HGT_ZIP",
        files=[{"path": "N36W112.hgt.zip", "role": "DATA"}], primary_file="N36W112.hgt.zip",
        quantity="ELEVATION", units="m", nodata_value=-32768, vertical_reference="EGM96 geoid (synthetic)",
        crs={"epsg": 4326}, longitude_convention="NEG180_180", declared_native_resolution_m=92,
    )  # fmt: skip


PDS3_LABEL = """PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 40
FILE_RECORDS = 20
^IMAGE = "LDEM.IMG"
OBJECT = IMAGE
  LINES = 20
  LINE_SAMPLES = 20
  SAMPLE_TYPE = LSB_INTEGER
  SAMPLE_BITS = 16
  BANDS = 1
  SCALING_FACTOR = 0.001
  OFFSET = 1737.4
  MISSING_CONSTANT = -32768
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  MAP_PROJECTION_TYPE = "SIMPLE CYLINDRICAL"
  A_AXIS_RADIUS = 1737.4 <KM>
  B_AXIS_RADIUS = 1737.4 <KM>
  C_AXIS_RADIUS = 1737.4 <KM>
  FIRST_STANDARD_PARALLEL = 0
  CENTER_LATITUDE = 0
  CENTER_LONGITUDE = 180
  LINE_FIRST_PIXEL = 1
  LINE_LAST_PIXEL = 20
  SAMPLE_FIRST_PIXEL = 1
  SAMPLE_LAST_PIXEL = 20
  MAP_PROJECTION_ROTATION = 0.0
  MAP_RESOLUTION = 4.0 <PIX/DEG>
  MAP_SCALE = 7.58 <KM/PIXEL>
  MAXIMUM_LATITUDE = 5
  MINIMUM_LATITUDE = 0
  EASTERNMOST_LONGITUDE = 10
  WESTERNMOST_LONGITUDE = 5
  LINE_PROJECTION_OFFSET = 19.5
  SAMPLE_PROJECTION_OFFSET = 19.5
  COORDINATE_SYSTEM_NAME = PLANETOCENTRIC
  POSITIVE_LONGITUDE_DIRECTION = EAST
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""


def build_pds3_radius(root: Path, dataset_id: str = "test-lunar-radius") -> dict[str, Any]:
    """Lunar RADIUS product: radius_km = raw*0.001 + 1737.4  =>  height_m = raw (a ramp of 0..399 m)."""
    d = root / dataset_id
    d.mkdir(parents=True)
    (d / "LDEM.LBL").write_text(PDS3_LABEL, encoding="ascii")
    raw = np.arange(400, dtype="<i2")
    raw[5] = -32768
    raw.tofile(d / "LDEM.IMG")
    return base_manifest(
        dataset_id, body="MOON", role="TARGET_TERRAIN", format="PDS3_IMG",
        files=[{"path": "LDEM.LBL", "role": "LABEL"}, {"path": "LDEM.IMG", "role": "DATA"}], primary_file="LDEM.IMG",
        quantity="RADIUS", units="km", reference_radius_m=1737400, scale_factor=0.001, offset=1737.4,
        scale_already_applied=True, nodata_value=-32768, vertical_reference="Lunar reference sphere 1737.4 km",
        crs={"wkt": MOON_GEO_WKT}, longitude_convention="ZERO_360", latitude_type="PLANETOCENTRIC",
    )  # fmt: skip


PDS4_LABEL = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1" xmlns:cart="http://pds.nasa.gov/pds4/cart/v1">
 <Identification_Area><logical_identifier>urn:nasa:pds:synthetic:m</logical_identifier><version_id>1.0</version_id></Identification_Area>
 <Observation_Area>
  <Target_Identification><name>Moon</name><type>Satellite</type></Target_Identification>
  <Discipline_Area>
   <cart:Cartography><cart:Spatial_Reference_Information><cart:Horizontal_Coordinate_System_Definition>
    <cart:Planar>
     <cart:Map_Projection><cart:map_projection_name>Equirectangular</cart:map_projection_name>
      <cart:Equirectangular><cart:standard_parallel_1>0</cart:standard_parallel_1>
       <cart:longitude_of_central_meridian>0</cart:longitude_of_central_meridian></cart:Equirectangular>
     </cart:Map_Projection>
     <cart:Planar_Coordinate_Information>
      <cart:planar_coordinate_encoding_method>Coordinate Pair</cart:planar_coordinate_encoding_method>
      <cart:Coordinate_Representation><cart:pixel_resolution_x unit="m/pixel">1000</cart:pixel_resolution_x>
       <cart:pixel_resolution_y unit="m/pixel">1000</cart:pixel_resolution_y></cart:Coordinate_Representation>
     </cart:Planar_Coordinate_Information>
     <cart:Geo_Transformation><cart:upperleft_corner_x unit="m">-3000</cart:upperleft_corner_x>
      <cart:upperleft_corner_y unit="m">2000</cart:upperleft_corner_y></cart:Geo_Transformation>
    </cart:Planar>
    <cart:Geodetic_Model><cart:latitude_type>Planetocentric</cart:latitude_type><cart:spheroid_name>Moon</cart:spheroid_name>
     <cart:a_axis_radius unit="m">1737400</cart:a_axis_radius><cart:b_axis_radius unit="m">1737400</cart:b_axis_radius>
     <cart:c_axis_radius unit="m">1737400</cart:c_axis_radius>
     <cart:longitude_direction>Positive East</cart:longitude_direction>
    </cart:Geodetic_Model>
   </cart:Horizontal_Coordinate_System_Definition></cart:Spatial_Reference_Information></cart:Cartography>
  </Discipline_Area>
 </Observation_Area>
 <File_Area_Observational>
  <File><file_name>m.img</file_name></File>
  <Array_2D_Image><offset unit="byte">0</offset><axes>2</axes><axis_index_order>Last Index Fastest</axis_index_order>
   <Element_Array><data_type>SignedLSB2</data_type><scaling_factor>0.5</scaling_factor><value_offset>10.0</value_offset></Element_Array>
   <Axis_Array><axis_name>Line</axis_name><elements>4</elements><sequence_number>1</sequence_number></Axis_Array>
   <Axis_Array><axis_name>Sample</axis_name><elements>6</elements><sequence_number>2</sequence_number></Axis_Array>
   <Special_Constants><missing_constant>-32768</missing_constant></Special_Constants>
  </Array_2D_Image>
 </File_Area_Observational>
</Product_Observational>
"""


def build_pds4(root: Path, dataset_id: str = "test-pds4-moon") -> dict[str, Any]:
    """PDS4 label + raw int16; metres = raw*0.5 + 10; equirectangular Moon sphere, 1 km cells."""
    d = root / dataset_id
    d.mkdir(parents=True)
    (d / "m.xml").write_text(PDS4_LABEL, encoding="utf-8")
    raw = np.arange(24, dtype="<i2")
    raw[3] = -32768
    raw.tofile(d / "m.img")
    return base_manifest(
        dataset_id, body="MOON", role="TARGET_TERRAIN", format="PDS4_IMG",
        files=[{"path": "m.xml", "role": "LABEL"}, {"path": "m.img", "role": "DATA"}], primary_file="m.img",
        quantity="ELEVATION", units="m", scale_factor=0.5, offset=10.0, scale_already_applied=True,
        nodata_value=-32768, vertical_reference="Lunar reference sphere", crs={"wkt": MOON_EQC_WKT},
        longitude_convention="PROJECTED", latitude_type="PLANETOCENTRIC", declared_native_resolution_m=1000,
    )  # fmt: skip


def build_netcdf_emit(root: Path, dataset_id: str = "test-emit") -> dict[str, Any]:
    """EMIT-style NetCDF4/HDF5: group variable, categorical int16 ids, global geotransform + spatial_ref."""
    import h5netcdf

    d = root / dataset_id
    d.mkdir(parents=True)
    ids = (np.arange(30).reshape(5, 6) % 4).astype("int16")
    ids[0, 0] = -9999
    wkt = CRS.from_epsg(4326).to_wkt()
    with h5netcdf.File(str(d / "emit.nc"), "w") as f:
        f.dimensions = {"y": 5, "x": 6}
        f.attrs["geotransform"] = np.array([-112.0, 0.0005, 0.0, 37.0, 0.0, -0.0005])
        f.attrs["spatial_ref"] = wkt
        var = f.create_group("mineral_metadata").create_variable(
            "group_1_mineral_id", ("y", "x"), "int16", fillvalue=-9999
        )
        var[:] = ids
    return base_manifest(
        dataset_id, body="EARTH", role="EARTH_MINERAL", format="NETCDF",
        files=[{"path": "emit.nc", "role": "DATA"}], primary_file="emit.nc",
        variable="mineral_metadata/group_1_mineral_id", quantity="MINERAL_CLASS", units="class", nodata_value=-9999,
        vertical_reference="not applicable", crs={"epsg": 4326}, longitude_convention="NEG180_180",
        declared_native_resolution_m=55.5,
    )  # fmt: skip


def build_ascii_grid(root: Path, dataset_id: str = "test-ascii") -> dict[str, Any]:
    d = root / dataset_id
    d.mkdir(parents=True)
    rows = ["ncols 6", "nrows 5", "xllcorner 500000", "yllcorner 4000000", "cellsize 30", "NODATA_value -9999"]
    grid = ramp(5, 6).round(1)
    body = [" ".join("-9999" if (r, c) == (1, 1) else f"{grid[r, c]:.1f}" for c in range(6)) for r in range(5)]
    (d / "dem.asc").write_text("\n".join(rows + body) + "\n", encoding="ascii")
    (d / "dem.prj").write_text(EARTH_UTM.to_wkt("WKT1_GDAL"), encoding="ascii")
    return base_manifest(
        dataset_id, body="EARTH", role="EARTH_TERRAIN", format="ASCII_GRID",
        files=[{"path": "dem.asc", "role": "DATA"}, {"path": "dem.prj", "role": "METADATA"}], primary_file="dem.asc",
        quantity="ELEVATION", units="m", nodata_value=-9999, crs={"epsg": 32612}, longitude_convention="PROJECTED",
        declared_native_resolution_m=30,
    )  # fmt: skip


def build_moon_polar_thermal(root: Path, dataset_id: str = "test-diviner") -> dict[str, Any]:
    """South-polar-stereographic Tmin product whose extent contains the pole (nodata 0)."""
    d = root / dataset_id
    d.mkdir(parents=True)
    data = (40.0 + ramp(16, 16, 0.0, 1.5)).astype("float32")
    data[0, 0] = 0.0
    _gtiff(
        d / "tmin.tif",
        data,
        crs=CRS.from_wkt(MOON_SOUTH_POLAR_WKT),
        transform=from_origin(-8000, 8000, 1000, 1000),
        nodata=0.0,
    )
    return base_manifest(
        dataset_id, body="MOON", role="LUNAR_THERMAL", format="GEOTIFF",
        files=[{"path": "tmin.tif", "role": "DATA"}], primary_file="tmin.tif", quantity="TEMPERATURE_K", units="K",
        nodata_value=0, vertical_reference="not applicable", crs={"wkt": MOON_SOUTH_POLAR_WKT},
        longitude_convention="PROJECTED", latitude_type="PLANETOCENTRIC", declared_native_resolution_m=1000,
    )  # fmt: skip


GOOD_BUILDERS = {
    "geotiff_earth": build_geotiff_earth,
    "geotiff_mars_scaled": build_geotiff_mars_scaled,
    "hgt_pair": build_hgt_pair,
    "hgt_zip": build_hgt_zip,
    "pds3_radius": build_pds3_radius,
    "pds4": build_pds4,
    "netcdf_emit": build_netcdf_emit,
    "ascii_grid": build_ascii_grid,
    "moon_polar_thermal": build_moon_polar_thermal,
}


def html_login_page() -> bytes:
    return b"<!DOCTYPE html><html><head><title>Earthdata Login</title></head><body>Sign in</body></html>"


def deep_copy(manifest: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(manifest)


def write_zip(path: Path, members: dict[str, bytes], *, symlink: tuple[str, str] | None = None) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink[0])
            info.external_attr = 0o120777 << 16
            zf.writestr(info, symlink[1])


def int16_bytes(values: list[int]) -> bytes:
    return struct.pack(f">{len(values)}h", *values)
