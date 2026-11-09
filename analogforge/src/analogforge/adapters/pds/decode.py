"""Turn a labelled PDS raster into a normalized :class:`DecodedRaster` (height, radius or value rasters)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from analogforge.adapters.pds import pds3, pds4
from analogforge.adapters.pds.image import ProductImage, metres_factor
from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata, geographic_wkt
from analogforge.adapters.source_http.errors import AdapterError

Quantity = Literal["height", "radius", "count"]
_BODY_NAMES = {"MARS": "Mars", "MOON": "Moon"}


@dataclass(frozen=True)
class PdsDecodeParams:
    """Explicit interpretation of a product. ``quantity`` is never guessed from a file name."""

    adapter_id: str
    expected_body: Literal["MARS", "MOON"]
    quantity: Quantity
    reference_radius_m: float | None = None  # subtracted from a 'radius' product; defaults to label A_AXIS_RADIUS
    units_override: str | None = None  # only for labels that omit UNIT
    vertical_reference: str | None = None  # e.g. "areoid" / "reference sphere"; recorded verbatim


def read_image(label_path: Path) -> ProductImage:
    suffix = label_path.suffix.lower()
    if suffix == ".xml":
        return pds4.read_product(label_path)
    if suffix in {".lbl", ".lab"}:
        return pds3.read_product(label_path)
    raise AdapterError("UNSUPPORTED_PRODUCT", f"cannot tell the label format of {label_path.name}",
                       detail_code="UNSUPPORTED_FORMAT")


def check_body_and_frame(image: ProductImage, expected_body: str) -> None:
    if image.body is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "label does not name its target body",
                           detail_code="METADATA_INCOMPLETE")
    if image.body != expected_body:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"label target {image.body} differs from expected {expected_body}",
                           detail_code="BODY_MISMATCH")
    if image.longitude_direction == "WEST":
        raise AdapterError("UNSUPPORTED_PRODUCT", "positive-west longitude products are not supported",
                           detail_code="UNSUPPORTED_FORMAT")


def geometry(image: ProductImage) -> tuple[tuple[float, float, float, float, float, float], str, float, float]:
    """Pixel-edge affine, longitude domain, and pixel size (deg) from label bounds, cross-checked."""
    west0, east0, south0, north0 = image.west, image.east, image.south, image.north
    if west0 is None or east0 is None or south0 is None or north0 is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "label lacks bounding coordinates",
                   detail_code="METADATA_INCOMPLETE")
    lines, samples = image.values.shape
    west, east = west0, east0
    if east <= west:
        east += 360.0
    dx = (east - west) / samples
    dy = (north0 - south0) / lines
    if dx <= 0 or dy <= 0:
        raise AdapterError("SOURCE_CONTENT_INVALID", "label bounding coordinates are inverted",
                           detail_code="GEOMETRY_MISMATCH")
    if image.resolution_px_per_deg is not None:
        expected = 1.0 / image.resolution_px_per_deg
        if abs(dx - expected) > 1e-6 * max(1.0, expected) or abs(dy - expected) > 1e-6 * max(1.0, expected):
            raise AdapterError("SOURCE_CONTENT_INVALID",
                               "array shape disagrees with MAP_RESOLUTION and the bounding coordinates",
                               detail_code="GEOMETRY_MISMATCH")
    domain = "NEG180_180" if west < 0 else "ZERO_360"
    return (dx, 0.0, west, 0.0, -dy, north0), domain, dx, dy


def decode(label_path: Path, params: PdsDecodeParams) -> DecodedRaster:
    image = read_image(label_path)
    check_body_and_frame(image, params.expected_body)
    affine, domain, dx, _ = geometry(image)
    unit = params.units_override or image.unit
    notes = [f"Scale {image.scale:g} and offset {image.offset:g} from the label were applied exactly once."]
    values = image.values
    if params.quantity == "count":
        quantity, out_unit, vref = "observation_count", "count", None
        notes.append("Counts are observational support, not a calibrated confidence probability.")
    else:
        factor = metres_factor(unit)
        if factor is None:
            raise AdapterError("SOURCE_CONTENT_INVALID", f"label unit {unit!r} is missing or not a length unit",
                               detail_code="METADATA_INCOMPLETE")
        values = values * factor
        out_unit = "m"
        if params.quantity == "radius":
            ref = params.reference_radius_m if params.reference_radius_m is not None else image.a_radius_m
            if ref is None:
                raise AdapterError("SOURCE_CONTENT_INVALID", "radius product needs a reference radius",
                                   detail_code="METADATA_INCOMPLETE")
            values = values - ref
            quantity = "relative_height"
            vref = f"radius minus reference sphere {ref:.1f} m"
            notes.append(f"Centre-to-surface radius converted to height by subtracting {ref:.1f} m.")
        else:
            quantity = "relative_height"
            vref = params.vertical_reference
            notes.append("Product values are treated as heights; no radius subtraction was applied.")
    a = image.a_radius_m
    if a is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "label lacks A_AXIS_RADIUS for the body-specific CRS",
                           detail_code="METADATA_INCOMPLETE")
    meta = RasterMetadata(
        adapter_id=params.adapter_id, body=params.expected_body, quantity=quantity, units=out_unit,
        vertical_reference=vref, crs_wkt=geographic_wkt(_BODY_NAMES[params.expected_body], a), transform=affine,
        width=values.shape[1], height=values.shape[0], pixel_registration="PIXEL_EDGE_BOUNDS_FROM_LABEL",
        longitude_domain=domain, source_scale=image.scale, source_offset=image.offset, scale_applied=True,
        nodata_raw=image.missing_raw[0] if image.missing_raw else None, product_id=image.product_id,
        notes=tuple(notes),
        attributes={**image.attributes, "pixel_size_deg": f"{dx:.12g}", "latitude_type": image.latitude_type or ""},
    )
    data = np.where(image.valid, values, np.nan)
    return DecodedRaster(data=data, valid=image.valid.copy(), metadata=meta)
