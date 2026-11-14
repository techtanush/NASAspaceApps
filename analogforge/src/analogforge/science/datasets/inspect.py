"""``datasets scaffold``: draft a ``manifest.yaml`` from the files in a dataset directory.

:func:`draft_manifest` infers what the files themselves say (format, CRS, nodata, transform, scale/offset, variable,
longitude convention) and writes the literal ``TODO_FILL_IN`` into every provenance field it cannot know
(``provider``, ``license_note``, ``citation``, and ``vertical_reference`` for height products).  The draft therefore
fails ``lineage_fields`` until a human completes it; once completed it validates.  The directory is only read.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml
from pyproj import CRS
from pyproj.exceptions import CRSError

from analogforge.ports.common import Body
from analogforge.science.datasets.checks import TODO_MARKER
from analogforge.science.datasets.ingest import ReadSpec, nominal_posting_m, read_dataset_rasters
from analogforge.science.datasets.registry import MANIFEST_NAME, RegistryError, validate_dataset_id
from analogforge.science.errors import ScienceError
from analogforge.science.geometry import body_geometry

_DOC_SUFFIXES: Final = (".md", ".txt", ".pdf", ".html", ".htm")
_META_SUFFIXES: Final = (".prj", ".hdr", ".aux.xml", ".json")
_REFERENCE_RADIUS_M: Final = {"EARTH": 6371008.0, "MOON": 1737400.0, "MARS": 3396190.0}


def _list_files(dataset_dir: Path) -> list[str]:
    root = dataset_dir.resolve()
    found = []
    for path in sorted(dataset_dir.rglob("*")):
        rel = path.relative_to(dataset_dir).as_posix()
        if not path.is_file() or path.name == MANIFEST_NAME or any(p.startswith(".") for p in rel.split("/")):
            continue
        if root in path.resolve().parents:
            found.append(rel)
    return found


def _is_pds4_label(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"Product_Observational" in handle.read(8192)


def _classify(dataset_dir: Path, files: list[str]) -> tuple[str, list[dict[str, str]], str | None]:
    """(format, files with roles, primary_file) from names and a few sniffed bytes."""
    roles: dict[str, str] = {}
    fmt = "OTHER"
    primary: str | None = None
    for rel in files:
        low = rel.lower()
        path = dataset_dir / rel
        if low.endswith(_DOC_SUFFIXES):
            roles[rel] = "DOCUMENTATION"
        elif low.endswith(_META_SUFFIXES):
            roles[rel] = "METADATA"
        elif low.endswith(".lbl"):
            roles[rel], fmt = "LABEL", "PDS3_IMG"
        elif low.endswith(".xml") and _is_pds4_label(path):
            roles[rel], fmt = "LABEL", "PDS4_IMG"
        elif low.endswith((".img", ".dat")):
            roles[rel] = "DATA"
        elif low.endswith((".tif", ".tiff")):
            roles[rel], fmt = "DATA", "GEOTIFF"
        elif low.endswith(".hgt"):
            roles[rel], fmt = "DATA", "HGT"
        elif low.endswith(".zip"):
            roles[rel] = "DATA"
            try:
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
            except (zipfile.BadZipFile, OSError):
                names = []
            if any(n.lower().endswith(".hgt") for n in names):
                fmt = "HGT_ZIP"
        elif low.endswith((".nc", ".nc4")):
            roles[rel], fmt = "DATA", "NETCDF"
        elif low.endswith((".h5", ".hdf5")):
            roles[rel], fmt = "DATA", "HDF5"
        elif low.endswith(".asc"):
            roles[rel], fmt = "DATA", "ASCII_GRID"
        else:
            roles[rel] = "DOCUMENTATION"
    data = [r for r, role in roles.items() if role == "DATA"]
    if fmt in ("PDS3_IMG", "PDS4_IMG"):
        primary = next((r for r in data), None) or next(r for r, role in roles.items() if role == "LABEL")
    elif data:
        primary = data[0]
    return fmt, [{"path": r, "role": roles[r]} for r in files], primary


def _first_variable(path: Path) -> str | None:
    try:
        import h5netcdf

        found: list[str] = []
        with h5netcdf.File(str(path), "r") as handle:

            def walk(group: Any, prefix: str) -> None:
                for name, var in group.variables.items():
                    if len(var.shape) >= 2 and np.issubdtype(var.dtype, np.number):
                        found.append(f"{prefix}{name}")
                for sub_name, sub in group.groups.items():
                    walk(sub, f"{prefix}{sub_name}/")

            walk(handle, "")
        return sorted(found)[0] if found else None
    except (ImportError, OSError, ValueError, KeyError):
        return None


def draft_manifest(dataset_dir: Path, body: Body, role: str, *, scratch_dir: Path | None = None) -> dict[str, Any]:
    """Draft manifest dict for ``dataset_dir`` (never writes); :class:`RegistryError` for a bad directory name."""
    if not dataset_dir.is_dir():
        raise RegistryError(f"{dataset_dir.name!r} is not a directory")
    dataset_id = validate_dataset_id(dataset_dir.name)
    files = _list_files(dataset_dir)
    fmt, file_entries, primary = _classify(dataset_dir, files)
    notes = ["Draft written by datasets scaffold: every inferred value must be checked against the product label."]
    draft: dict[str, Any] = {
        "manifest_version": "1.0",
        "dataset_id": dataset_id,
        "title": dataset_id.replace("-", " "),
        "provider": TODO_MARKER,
        "is_synthetic": False,
        "body": body,
        "role": role,
        "format": fmt,
        "files": file_entries,
    }
    if primary is not None:
        draft["primary_file"] = primary
    variable = None
    if fmt in ("NETCDF", "HDF5") and primary is not None:
        variable = _first_variable(dataset_dir / primary)
        if variable is not None:
            draft["variable"] = variable
            notes.append(f"variable {variable!r} was the first 2-D numeric variable found; confirm it")

    height_like = role in ("TARGET_TERRAIN", "EARTH_TERRAIN")
    quantity, units = {"EARTH_MINERAL": ("MINERAL_CLASS", "class"), "LUNAR_THERMAL": ("TEMPERATURE_K", "K")}.get(
        role, ("ELEVATION", "m") if height_like else ("OTHER", "dimensionless")
    )
    crs: dict[str, Any] | None = None
    longitude = "NEG180_180"
    reference_radius: float | None = None
    rasters = []
    if scratch_dir is None and fmt == "HGT_ZIP":
        notes.append("archive contents not inspected: pass scratch_dir to allow safe extraction")
    elif primary is not None or file_entries:
        try:
            spec = ReadSpec(dataset_id, fmt, tuple((e["path"], e["role"]) for e in file_entries), variable, 1)
            present = {e["path"]: (dataset_dir / e["path"]).resolve() for e in file_entries}
            rasters = read_dataset_rasters(spec, present, scratch_dir or dataset_dir)
        except ScienceError as exc:
            notes.append(f"files could not be read for inference: {exc.message}")
    if rasters:
        first = rasters[0]
        if first.nodata_value is not None:
            draft["nodata_value"] = first.nodata_value
        if first.reader_scale != 1.0 or first.reader_offset != 0.0:
            draft["scale_factor"], draft["offset"] = first.reader_scale, first.reader_offset
            draft["scale_already_applied"] = True
            notes.append("file metadata carries scale/offset; scale_already_applied set true (reader applies it)")
        if first.crs_wkt is not None:
            try:
                file_crs = CRS.from_wkt(first.crs_wkt)
                epsg = file_crs.to_epsg(min_confidence=100)
                crs = {"epsg": epsg} if (body == "EARTH" and epsg is not None) else {"wkt": file_crs.to_wkt()}
                longitude = "PROJECTED" if file_crs.is_projected else longitude
                gt = first.geotransform
                h, w = first.values.shape
                post = nominal_posting_m(body, file_crs, gt, h, w)
                if post is not None:
                    draft["declared_native_resolution_m"] = float(f"{post:.3g}")
                if file_crs.is_geographic:
                    east = max(gt[0], gt[0] + w * gt[1])
                    longitude = "ZERO_360" if east > 180.0 else "NEG180_180"
            except CRSError:
                notes.append("file CRS could not be parsed")
        else:
            notes.append("the file carries no CRS: crs left out; supply it")
        if height_like:
            raw = first.values.astype(np.float64)
            keep = np.isfinite(raw)
            if first.nodata_value is not None:
                keep &= raw != first.nodata_value
            if keep.any():
                median = float(np.median(np.abs(raw[keep] * first.reader_scale + first.reader_offset)))
                mean = body_geometry(body).mean_radius_m
                if abs(median - mean) < 0.2 * mean:
                    quantity, units, reference_radius = "RADIUS", "m", _REFERENCE_RADIUS_M[body]
                elif abs(median - mean / 1000.0) < 0.2 * mean / 1000.0:
                    quantity, units, reference_radius = "RADIUS", "km", _REFERENCE_RADIUS_M[body]
                if reference_radius is not None:
                    notes.append("values look like radii: quantity RADIUS with reference_radius_m; confirm before use")
    draft["quantity"], draft["units"] = quantity, units
    if reference_radius is not None:
        draft["reference_radius_m"] = reference_radius
    draft["vertical_reference"] = TODO_MARKER if quantity in ("ELEVATION", "RADIUS", "SLOPE_DEG") else "not applicable"
    if crs is not None:
        draft["crs"] = crs
    draft["longitude_convention"] = longitude
    draft["latitude_type"] = "GEODETIC" if body == "EARTH" else "PLANETOCENTRIC"
    draft["pixel_registration"] = "UNKNOWN"
    draft["license_note"] = TODO_MARKER
    draft["citation"] = TODO_MARKER
    draft["notes"] = notes
    return draft


def dump_draft_yaml(draft: dict[str, Any]) -> str:
    """Deterministic YAML text for a draft (``safe_dump``, key order preserved)."""
    return yaml.safe_dump(draft, sort_keys=False, allow_unicode=True)


__all__ = ["draft_manifest", "dump_draft_yaml"]
