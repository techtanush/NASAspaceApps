"""PDS3 detached-label reader (labels are parsed as data with ``pvl``; nothing is evaluated)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pvl
from pvl.collections import Quantity

from analogforge.adapters.pds.image import ProductImage, metres_factor, read_array, safe_sibling, scale_once
from analogforge.adapters.source_http.errors import AdapterError

MAX_LABEL_BYTES = 4 * 1024 * 1024
_DTYPES = {
    ("MSB_INTEGER", 16): ">i2", ("MSB_INTEGER", 32): ">i4", ("LSB_INTEGER", 16): "<i2", ("LSB_INTEGER", 32): "<i4",
    ("SUN_INTEGER", 16): ">i2", ("SUN_INTEGER", 32): ">i4", ("PC_INTEGER", 16): "<i2", ("PC_INTEGER", 32): "<i4",
    ("MSB_UNSIGNED_INTEGER", 8): "u1", ("LSB_UNSIGNED_INTEGER", 8): "u1", ("UNSIGNED_INTEGER", 8): "u1",
    ("MSB_UNSIGNED_INTEGER", 16): ">u2", ("LSB_UNSIGNED_INTEGER", 16): "<u2",
    ("PC_REAL", 32): "<f4", ("PC_REAL", 64): "<f8", ("IEEE_REAL", 32): ">f4", ("IEEE_REAL", 64): ">f8",
    ("MSB_REAL", 32): ">f4", ("LSB_REAL", 32): "<f4",
}


def _number(value: Any) -> float | None:
    if isinstance(value, Quantity):
        value = value.value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _unit(value: Any) -> str | None:
    return str(value.units) if isinstance(value, Quantity) else None


def _find(module: Any, key: str) -> Any:
    """Depth-first lookup of the first occurrence of ``key`` anywhere in a parsed label."""
    if hasattr(module, "items"):
        for k, v in module.items():
            if k == key:
                return v
        for _, v in module.items():
            if hasattr(v, "items"):
                hit = _find(v, key)
                if hit is not None:
                    return hit
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value.value if isinstance(value, Quantity) else value).strip() or None


def load_label(path: Path) -> Any:
    if path.stat().st_size > MAX_LABEL_BYTES:
        raise AdapterError("RESOURCE_LIMIT", f"{path.name} exceeds the label size limit", detail_code="LABEL_TOO_LARGE")
    text = path.read_bytes().decode("utf-8", errors="replace")
    if "PDS_VERSION_ID" not in text:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"{path.name} is not a PDS3 label",
                   detail_code="LABEL_PARSE_ERROR")
    try:
        return pvl.loads(text)
    except Exception as exc:  # noqa: BLE001 - pvl raises many parser-specific types; all are label-invalid
        raise AdapterError("SOURCE_CONTENT_INVALID", f"{path.name}: PDS3 label could not be parsed",
                           detail_code="LABEL_PARSE_ERROR") from exc


def data_file_name(label: Any) -> str:
    pointer = label.get("^IMAGE")
    if isinstance(pointer, (list, tuple)):
        pointer = pointer[0] if pointer else None
    if not isinstance(pointer, str):
        raise AdapterError("UNSUPPORTED_PRODUCT", "label has no detached ^IMAGE file pointer",
                           detail_code="UNSUPPORTED_FORMAT")
    return pointer


def read_product(label_path: Path) -> ProductImage:
    label = load_label(label_path)
    image = label.get("IMAGE")
    if image is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", "label has no IMAGE object", detail_code="UNSUPPORTED_FORMAT")
    lines = _number(image.get("LINES"))
    samples = _number(image.get("LINE_SAMPLES"))
    bits = _number(image.get("SAMPLE_BITS"))
    sample_type = _text(image.get("SAMPLE_TYPE"))
    if lines is None or samples is None or bits is None or sample_type is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "IMAGE object lacks LINES/LINE_SAMPLES/SAMPLE_BITS/SAMPLE_TYPE",
                           detail_code="METADATA_INCOMPLETE")
    if (_number(image.get("BANDS")) or 1) != 1 or (_number(image.get("LINE_PREFIX_BYTES")) or 0) or (
            _number(image.get("LINE_SUFFIX_BYTES")) or 0):
        raise AdapterError("UNSUPPORTED_PRODUCT", "multi-band or prefixed/suffixed image layouts are unsupported",
                           detail_code="UNSUPPORTED_FORMAT")
    dtype = _DTYPES.get((sample_type.upper(), int(bits)))
    if dtype is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"unsupported sample encoding {sample_type}/{int(bits)}",
                           detail_code="UNSUPPORTED_FORMAT")
    data_path = safe_sibling(label_path, data_file_name(label))
    raw = read_array(data_path, dtype, int(lines), int(samples), 0)
    scale = _number(image.get("SCALING_FACTOR"))
    offset = _number(image.get("OFFSET"))
    missing = tuple(v for v in (_number(image.get("MISSING_CONSTANT")), _number(image.get("INVALID_CONSTANT")))
                    if v is not None)
    values, valid = scale_once(raw, 1.0 if scale is None else scale, 0.0 if offset is None else offset, missing)
    a_raw = _find(label, "A_AXIS_RADIUS")
    a_num = _number(a_raw)
    a_m = None
    if a_num is not None:
        factor = metres_factor(_unit(a_raw) or "km")
        a_m = a_num * factor if factor is not None else None
    res = _number(_find(label, "MAP_RESOLUTION"))
    return ProductImage(
        product_id=_text(label.get("PRODUCT_ID")) or _text(label.get("DATA_SET_ID")),
        body=(_text(label.get("TARGET_NAME")) or "").upper() or None, values=values, valid=valid,
        scale=1.0 if scale is None else scale, offset=0.0 if offset is None else offset,
        unit=_text(image.get("UNIT")), missing_raw=missing,
        west=_number(_find(label, "WESTERNMOST_LONGITUDE")), east=_number(_find(label, "EASTERNMOST_LONGITUDE")),
        south=_number(_find(label, "MINIMUM_LATITUDE")), north=_number(_find(label, "MAXIMUM_LATITUDE")),
        resolution_px_per_deg=res, a_radius_m=a_m,
        longitude_direction=(_text(_find(label, "POSITIVE_LONGITUDE_DIRECTION")) or "").upper() or None,
        latitude_type=_text(_find(label, "COORDINATE_SYSTEM_NAME")),
        attributes={"format": "PDS3", "sample_type": sample_type, "sample_bits": str(int(bits)),
                    "data_file": data_path.name},
    )


__all__ = ["data_file_name", "load_label", "read_product"]

