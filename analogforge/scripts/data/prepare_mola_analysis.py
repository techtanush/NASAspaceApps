"""Prepare a new, auditable 128-pixel/degree MOLA MEGDR analysis derivative.

Offline only. Original IMG/labels and the parent dataset remain unchanged.
PDS georeferencing recipe: https://pds-geosciences.wustl.edu/mgs/
mgs-m-mola-5-megdr-l3-v1/mgsl_300x/extras/mola_envi.htm
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import pyproj
import rasterio
import yaml
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

RECIPE = "mola-megdr-128ppd-canonical-frame/1.0"
PDS_GUIDE = (
    "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/extras/mola_envi.htm"
)
SOURCE_RADIUS = 3_396_000.0
ANALYSIS_RADIUS = 3_396_190.0
PPD = 128.0
NODATA = -32768.0


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def label_value(text: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*([^\r\n]+)", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"Required PDS keyword is absent: {name}")
    return match[1].strip().strip('"')


def inspect_label(text: str) -> dict[str, Any]:
    required = {
        "PDS_VERSION_ID": "PDS3", "DATA_SET_ID": "MGS-M-MOLA-5-MEGDR-L3-V1.0",
        "TARGET_NAME": "MARS", "INSTRUMENT_ID": "MOLA", "SAMPLE_TYPE": "MSB_INTEGER",
        "SAMPLE_BITS": "16", "UNIT": "METER", "NAME": "MEDIAN_TOPOGRAPHY",
        "MAP_PROJECTION_TYPE": "SIMPLE CYLINDRICAL", "POSITIVE_LONGITUDE_DIRECTION": "EAST",
        "COORDINATE_SYSTEM_TYPE": "BODY-FIXED ROTATING", "COORDINATE_SYSTEM_NAME": "PLANETOCENTRIC",
        "A_AXIS_RADIUS": "3396.0 <KM>", "B_AXIS_RADIUS": "3396.0 <KM>", "C_AXIS_RADIUS": "3396.0 <KM>",
        "MAP_RESOLUTION": "128.0 <PIXEL/DEGREE>",
    }
    for name, expected in required.items():
        if label_value(text, name) != expected:
            raise ValueError(f"Unsupported MOLA metadata: {name}")
    for name, expected_number in {
        "CENTER_LATITUDE": 0.0, "CENTER_LONGITUDE": 180.0, "MAP_PROJECTION_ROTATION": 0.0,
    }.items():
        if float(label_value(text, name).split()[0]) != expected_number:
            raise ValueError(f"Unsupported MOLA projection: {name}")
    if "IAU2000" not in text or "GMM3" not in text:
        raise ValueError("The declared IAU2000 frame and GMM3 areoid must be documented")
    values = {name: float(label_value(text, name).split()[0]) for name in (
        "WESTERNMOST_LONGITUDE", "EASTERNMOST_LONGITUDE", "MINIMUM_LATITUDE", "MAXIMUM_LATITUDE",
    )}
    width, height = int(label_value(text, "LINE_SAMPLES")), int(label_value(text, "LINES"))
    west, east = values["WESTERNMOST_LONGITUDE"], values["EASTERNMOST_LONGITUDE"]
    south, north = values["MINIMUM_LATITUDE"], values["MAXIMUM_LATITUDE"]
    if width != round((east - west) * PPD) or height != round((north - south) * PPD):
        raise ValueError("Source grid dimensions disagree with label corners and 128 pixels/degree")
    return {"width": width, "height": height, "bbox": [west, south, east, north],
            "product_id": label_value(text, "PRODUCT_ID"), "version": label_value(text, "PRODUCT_VERSION_ID")}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing dataset")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.dataset_id):
        raise ValueError("dataset-id must contain lowercase letters, digits and hyphens")
    metadata = inspect_label(args.source_label.read_text())
    if args.source_image.name.upper() != metadata["product_id"].upper():
        raise ValueError("Source image filename differs from the PDS product identity")
    if args.source_image.stat().st_size != metadata["height"] * metadata["width"] * 2:
        raise ValueError("Source image size differs from the detached signed-int16 raster")
    source_hash = sha256(args.source_image)
    if source_hash != args.expected_source_sha256:
        raise ValueError("Original source image checksum differs from the acquisition receipt")
    parent = yaml.safe_load((args.parent_dataset / "manifest.yaml").read_text())
    if (parent["is_synthetic"] or parent["body"] != "MARS" or parent["quantity"] != "ELEVATION"
            or parent["units"] != "m" or parent["product_identity"]["version"] != metadata["version"]
            or parent["product_identity"]["product_id"] != "MGS-M-MOLA-5-MEGDR-L3-V1.0"):
        raise ValueError("Parent dataset does not describe the same real MOLA topography product")
    url = urlsplit(parent["product_identity"]["source_url"])
    if (url.scheme != "https" or url.hostname != "pds-geosciences.wustl.edu" or url.username or url.password
            or url.query or url.fragment or url.port not in (None, 443)):
        raise ValueError("Expected a public NASA PDS Geosciences source URL without credentials")
    parent_hashes = {"manifest.yaml": sha256(args.parent_dataset / "manifest.yaml")}
    for entry in parent["files"]:
        path = (args.parent_dataset / entry["path"]).resolve()
        if not path.is_relative_to(args.parent_dataset.resolve()) or sha256(path) != entry["sha256"]:
            raise ValueError("Parent dataset bytes differ from its immutable manifest")
        parent_hashes[entry["path"]] = entry["sha256"]
    if (sha256(args.source_label) != parent_hashes.get("source-pds3.lbl")
            or sha256(args.pds4_label) != parent_hashes.get("source-pds4.xml")):
        raise ValueError("Provided source labels differ from the parent dataset's verified labels")
    old = json.loads((args.parent_dataset / "provenance.json").read_text())
    if old["source_sha256"] != source_hash:
        raise ValueError("Parent acquisition identifies a different original image")
    west, south, east, north = args.bbox
    sw, ss, se, sn = metadata["bbox"]
    if not all(math.isfinite(v) for v in args.bbox) or not (sw <= west < east <= se and ss <= south < north <= sn):
        raise ValueError("Requested non-wrapping bbox must lie wholly inside the labeled source tile")
    c0, c1 = math.floor((west - sw) * PPD), math.ceil((east - sw) * PPD)
    r0, r1 = math.floor((sn - north) * PPD), math.ceil((sn - south) * PPD)
    if (r1 - r0) * (c1 - c0) > 4_000_000:
        raise ValueError("Requested crop exceeds the preparation utility's bounded cell budget")
    posting = 2 * math.pi * SOURCE_RADIUS / (360 * PPD)
    corrected = Affine(posting, 0, math.radians(sw - 180) * SOURCE_RADIUS,
                       0, -posting, math.radians(sn) * SOURCE_RADIUS)
    cropped = corrected @ Affine.translation(c0, r0)
    ratio = ANALYSIS_RADIUS / SOURCE_RADIUS
    destination = Affine(*(value * ratio for value in tuple(cropped)[:6]))
    source_crs = CRS.from_proj4(f"+proj=eqc +lat_ts=0 +lon_0=180 +R={SOURCE_RADIUS} +units=m +type=crs")
    target_crs = CRS.from_proj4(f"+proj=eqc +lat_ts=0 +lon_0=180 +R={ANALYSIS_RADIUS} +units=m +type=crs")
    pipeline = (f"+proj=pipeline +step +inv +proj=eqc +lat_ts=0 +lon_0=180 +R={SOURCE_RADIUS} "
                f"+step +proj=eqc +lat_ts=0 +lon_0=180 +R={ANALYSIS_RADIUS}")
    original = np.memmap(args.source_image, dtype=">i2", mode="r", shape=(metadata["height"], metadata["width"]))
    values = np.asarray(original[r0:r1, c0:c1], dtype=np.float64)
    warped = np.full(values.shape, NODATA, dtype=np.float64)
    reproject(values, warped, src_transform=cropped, src_crs=source_crs, dst_transform=destination,
              dst_crs=target_crs, src_nodata=NODATA, dst_nodata=NODATA,
              resampling=Resampling.average, COORDINATE_OPERATION=pipeline)
    if not np.array_equal(warped == NODATA, values == NODATA) or not np.allclose(warped, values, rtol=0, atol=1e-6):
        raise ValueError("The congruent angular-grid warp unexpectedly changed elevations or missing support")
    transform = Transformer.from_pipeline(pipeline)
    x, y = cropped @ (0.5, 0.5)
    tx, ty = transform.transform(x, y)
    if not np.allclose((tx, ty), destination @ (0.5, 0.5), rtol=0, atol=1e-6):
        raise ValueError("Explicit coordinate operation disagrees with the destination affine")
    limitations = [
        "Georeferencing follows the published PDS precise-MAP_SCALE/corner recipe; not new positional validation.",
        "Horizontal frame normalization assumes the same IAU2000 planetocentric angles and prime meridian.",
        "Source gridded posting is not effective measurement resolution; interpolated MOLA bins remain interpolated.",
        "No elevation, areoid, vertical datum or height-reference shift; no new observations or finer angular grid.",
        "Sub-metre obstacles, mineralogy, thermal conditions and physical rover performance remain unvalidated.",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mola-analysis-", dir=output.parent) as temporary:
        staged = Path(temporary)
        with rasterio.open(staged / "terrain.tif", "w", driver="GTiff", height=r1 - r0,
                           width=c1 - c0, count=1, dtype="float64", crs=target_crs,
                           transform=destination, nodata=NODATA, compress="deflate") as dataset:
            dataset.write(warped, 1)
        shutil.copyfile(args.source_label, staged / "source-pds3.lbl")
        shutil.copyfile(args.pds4_label, staged / "source-pds4.xml")
        shutil.copyfile(args.parent_dataset / "manifest.yaml", staged / "parent-manifest.yaml")
        shutil.copyfile(args.parent_dataset / "provenance.json", staged / "parent-provenance.json")
        provenance = {
            "recipe": RECIPE, "prepared_at": datetime.now(UTC).isoformat(), "dataset_id": args.dataset_id,
            "source_url": parent["product_identity"]["source_url"], "source_sha256": source_hash,
            "source_size_bytes": args.source_image.stat().st_size, "source_product": metadata,
            "parent_dataset_id": parent["dataset_id"], "parent_file_sha256": parent_hashes,
            "source_declared_wkt": parent["crs"]["wkt"], "gdal_original_transform": old["source_transform"],
            "precise_source_posting_m": posting, "precise_source_affine": list(corrected),
            "requested_bbox_lonlat": args.bbox, "crop_window_col_row_width_height": [c0, r0, c1 - c0, r1 - r0],
            "corrected_crop_affine": list(cropped), "corrected_source_wkt": source_crs.to_wkt(),
            "destination_wkt": target_crs.to_wkt(), "destination_affine": list(destination),
            "destination_posting_m": destination.a, "coordinate_operation": pipeline,
            "resampler": "average on congruent angular pixels", "nodata": NODATA,
            "maximum_elevation_change_m": float(np.max(np.abs(warped - values))),
            "versions": {"rasterio": rasterio.__version__, "gdal": rasterio.__gdal_version__,
                         "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str},
            "citations": [PDS_GUIDE, parent["citation"]], "limitations": limitations,
        }
        (staged / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        manifest = {**parent, "dataset_id": args.dataset_id,
                    "title": "MOLA MEGDR precise-georeference canonical Mars analysis derivative",
                    "crs": {"wkt": target_crs.to_wkt()}, "declared_native_resolution_m": destination.a,
                    "notes": [*parent.get("notes", []), *limitations], "files": []}
        for name, role in [("terrain.tif", "DATA"), ("provenance.json", "METADATA"),
                           ("source-pds3.lbl", "DOCUMENTATION"), ("source-pds4.xml", "DOCUMENTATION"),
                           ("parent-manifest.yaml", "DOCUMENTATION"), ("parent-provenance.json", "DOCUMENTATION")]:
            manifest["files"].append({"path": name, "role": role, "sha256": sha256(staged / name)})
        (staged / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
        if sha256(args.source_image) != source_hash or output.exists():
            raise ValueError("Source changed during preparation or output already exists")
        staged.rename(output)
    return {"dataset_id": args.dataset_id, "output_dir": str(output),
            "shape": list(warped.shape), "posting_m": destination.a, "source_sha256": source_hash}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-image", type=Path, required=True)
    parser.add_argument("--source-label", type=Path, required=True)
    parser.add_argument("--pds4-label", type=Path, required=True)
    parser.add_argument("--parent-dataset", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"), required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args()), indent=2))


if __name__ == "__main__":
    main()
