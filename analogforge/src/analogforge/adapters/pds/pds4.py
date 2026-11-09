"""PDS4 XML label reader (external entities impossible: DTDs are refused before parsing)."""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405 - elements only; parsing happens in xml_safe
from pathlib import Path

from analogforge.adapters.pds.image import ProductImage, metres_factor, read_array, safe_sibling, scale_once
from analogforge.adapters.pds.xml_safe import find_all, find_one, local, parse_xml_file, text_of
from analogforge.adapters.source_http.errors import AdapterError

_DTYPES = {
    "SignedMSB2": ">i2", "SignedLSB2": "<i2", "UnsignedMSB2": ">u2", "UnsignedLSB2": "<u2", "SignedMSB4": ">i4",
    "SignedLSB4": "<i4", "UnsignedByte": "u1", "SignedByte": "i1", "IEEE754MSBSingle": ">f4",
    "IEEE754LSBSingle": "<f4", "IEEE754MSBDouble": ">f8", "IEEE754LSBDouble": "<f8",
}


def _float(root: ET.Element, name: str) -> float | None:
    raw = text_of(root, name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"label element {name} is not numeric",
                           detail_code="METADATA_INCOMPLETE") from exc


def data_file_name(root: ET.Element) -> str:
    name = text_of(root, "file_name")
    if name is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "label has no File/file_name", detail_code="METADATA_INCOMPLETE")
    return name


def read_product(label_path: Path) -> ProductImage:
    root = parse_xml_file(label_path)
    array = find_one(root, "Array_2D_Image") or find_one(root, "Array_2D")
    if array is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", "label has no Array_2D / Array_2D_Image",
                   detail_code="UNSUPPORTED_FORMAT")
    axes: dict[str, int] = {}
    for axis in find_all(array, "Axis_Array"):
        name = text_of(axis, "axis_name")
        elements = text_of(axis, "elements")
        if name is None or elements is None or not elements.isdigit():
            raise AdapterError("SOURCE_CONTENT_INVALID", "Axis_Array lacks axis_name/elements",
                               detail_code="METADATA_INCOMPLETE")
        axes[name.lower()] = int(elements)
    if "line" not in axes or "sample" not in axes:
        raise AdapterError("UNSUPPORTED_PRODUCT", "only Line x Sample arrays are supported",
                   detail_code="UNSUPPORTED_FORMAT")
    order = text_of(array, "axis_index_order")
    if order is not None and order.lower() != "last index fastest":
        raise AdapterError("UNSUPPORTED_PRODUCT", "only 'Last Index Fastest' arrays are supported",
                           detail_code="UNSUPPORTED_FORMAT")
    data_type = text_of(array, "data_type")
    dtype = _DTYPES.get(data_type or "")
    if dtype is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"unsupported PDS4 data_type {data_type!r}",
                           detail_code="UNSUPPORTED_FORMAT")
    offset_bytes = int(_float(array, "offset") or 0)
    data_path = safe_sibling(label_path, data_file_name(root))
    raw = read_array(data_path, dtype, axes["line"], axes["sample"], offset_bytes)
    scale = _float(array, "scaling_factor")
    offset = _float(array, "value_offset")
    missing = tuple(v for v in (_float(root, "missing_constant"), _float(root, "invalid_constant")) if v is not None)
    values, valid = scale_once(raw, 1.0 if scale is None else scale, 0.0 if offset is None else offset, missing)
    a_km = _float(root, "a_axis_radius")
    a_unit = None
    radius_el = find_one(root, "a_axis_radius")
    if radius_el is not None:
        a_unit = radius_el.attrib.get("unit")
    a_m = None
    if a_km is not None:
        factor = metres_factor(a_unit or "km")
        a_m = a_km * factor if factor is not None else None
    west = _float(root, "west_bounding_coordinate")
    east = _float(root, "east_bounding_coordinate")
    south = _float(root, "south_bounding_coordinate")
    north = _float(root, "north_bounding_coordinate")
    lidvid = None
    lid = text_of(root, "logical_identifier")
    ver = text_of(root, "version_id")
    if lid is not None:
        lidvid = f"{lid}::{ver}" if ver else lid
    el_array = find_one(array, "Element_Array")
    unit = el_array.attrib.get("unit") if el_array is not None else None
    if unit is None and el_array is not None:
        unit = text_of(el_array, "unit")
    target = None
    for el in find_all(root, "Target_Identification"):
        target = text_of(el, "name")
    direction = text_of(root, "longitude_direction")
    return ProductImage(
        product_id=lidvid, body=target.upper() if target else None, values=values, valid=valid,
        scale=1.0 if scale is None else scale, offset=0.0 if offset is None else offset, unit=unit,
        missing_raw=missing, west=west, east=east, south=south, north=north, resolution_px_per_deg=None,
        a_radius_m=a_m, longitude_direction=("WEST" if direction and "west" in direction.lower() else
                                             "EAST" if direction and "east" in direction.lower() else None),
        latitude_type=text_of(root, "latitude_type"),
        attributes={"format": "PDS4", "data_type": data_type or "", "data_file": data_path.name,
                    "root_element": local(root.tag)},
    )
