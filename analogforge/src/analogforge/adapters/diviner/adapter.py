"""LRO Diviner derived-product adapter: explicit variable selection, kelvin output.

Only the documented derived variables registered in :data:`SUPPORTED_VARIABLES` are decoded. A request for any
other variable is an explicit capability gap (``UNSUPPORTED_PRODUCT``); bands are never averaged into a new
variable. Index/base URLs are unverified configuration proposals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

from analogforge.adapters.pds import adapter as pds_adapter
from analogforge.adapters.pds.decode import check_body_and_frame, geometry, read_image
from analogforge.adapters.pds.image import is_kelvin
from analogforge.adapters.pds.index import PdsSource, discover_in_index
from analogforge.adapters.source_http.client import SafeHttp
from analogforge.adapters.source_http.cmr import empty_selection
from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata, geographic_wkt
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.policy import HttpPolicy
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

DIVINER_ADAPTER_ID = "moon_diviner_derived"
PDS_HOST = "pds-geosciences.wustl.edu"
MOON_RADIUS_M = 1_737_400.0
_CELSIUS = frozenset({"c", "degc", "celsius", "deg_c"})


@dataclass(frozen=True)
class DivinerVariable:
    name: str
    aggregation: str  # min | max | mean
    description: str
    index_label_url: str
    base_url: str


def _var(name: str, aggregation: str, folder: str) -> DivinerVariable:
    base = f"https://{PDS_HOST}/lro/lro-l-dlre-4-rdr-v1/lrodlr_1001/{folder}/"
    return DivinerVariable(
        name, aggregation, f"Diviner bolometric brightness temperature, {aggregation}", base + "index/index.lbl", base
    )


SUPPORTED_VARIABLES: dict[str, DivinerVariable] = {
    v.name: v
    for v in (
        _var("bolometric_brightness_temperature_min", "min", "min"),
        _var("bolometric_brightness_temperature_max", "max", "max"),
        _var("bolometric_brightness_temperature_mean", "mean", "mean"),
    )
}


def default_policy() -> HttpPolicy:
    return HttpPolicy(allowed_hosts=frozenset({PDS_HOST}))


def variable_for(kind: str, variables: dict[str, DivinerVariable] | None = None) -> DivinerVariable | None:
    table = variables or SUPPORTED_VARIABLES
    return table.get(kind.split(":", 1)[1] if kind.startswith("diviner:") else kind)


def _source(variable: DivinerVariable) -> PdsSource:
    return PdsSource(
        adapter_id=DIVINER_ADAPTER_ID,
        body="MOON",
        product_id=variable.name,
        version=None,
        host=PDS_HOST,
        index_label_url=variable.index_label_url,
        base_url=variable.base_url,
        longitude_domain="ZERO_360",
        native_resolution_m=None,
    )


def discover(
    request: ResolveCoverageInput,
    client: httpx.Client | None,
    *,
    policy: HttpPolicy | None = None,
    variables: dict[str, DivinerVariable] | None = None,
    max_products: int = 100,
) -> list[CoverageSelection]:
    if request.adapter_id != DIVINER_ADAPTER_ID:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"unknown adapter {request.adapter_id!r}", detail_code="UNSUPPORTED_FORMAT"
        )
    if request.aoi.body != "MOON":
        raise AdapterError(
            "UNSUPPORTED_PRODUCT",
            f"Diviner is a Moon product; AOI body is {request.aoi.body}",
            detail_code="BODY_MISMATCH",
        )
    if not request.measurement_kinds:
        return [
            empty_selection(
                DIVINER_ADAPTER_ID,
                None,
                None,
                request,
                "UNSUPPORTED",
                "the thermal variable must be chosen explicitly; none was requested",
                None,
            )
        ]
    out: list[CoverageSelection] = []
    http = SafeHttp(client, policy or default_policy()) if client is not None else None
    for kind in sorted(set(request.measurement_kinds)):
        variable = variable_for(kind, variables)
        if variable is None:
            out.append(
                empty_selection(
                    DIVINER_ADAPTER_ID,
                    kind,
                    None,
                    request,
                    "UNSUPPORTED",
                    f"Diviner variable {kind!r} is not a supported derived product (no ad-hoc band averaging)",
                    None,
                )
            )
        elif http is None:
            out.append(
                empty_selection(
                    DIVINER_ADAPTER_ID,
                    variable.name,
                    None,
                    request,
                    "UNAVAILABLE",
                    "no HTTP client supplied (offline mode)",
                    None,
                )
            )
        else:
            note = f"variable={variable.name}; aggregation={variable.aggregation}"
            out.extend(
                discover_in_index(http, _source(variable), request, max_products=max_products, extra_notes=(note,))
            )
    return out


def fetch(
    selection: CoverageSelection,
    client: httpx.Client | None,
    scratch: Path,
    *,
    policy: HttpPolicy | None = None,
    variables: dict[str, DivinerVariable] | None = None,
) -> list[AcquiredAsset]:
    variable = variable_for(selection.product_id or "", variables)
    if selection.adapter_id != DIVINER_ADAPTER_ID or variable is None:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT",
            f"unsupported Diviner variable {selection.product_id!r}",
            detail_code="UNSUPPORTED_FORMAT",
        )
    if client is None:
        raise AdapterError("SOURCE_UNAVAILABLE", "no HTTP client supplied", detail_code="OFFLINE")
    http = SafeHttp(client, policy or default_policy())
    return pds_adapter.fetch_pds_products(http, _source(variable), selection, scratch)


def asset_path(scratch: Path, asset: AcquiredAsset) -> Path:
    return pds_adapter.asset_path(scratch, asset)


@dataclass(frozen=True)
class DivinerDecodeParams:
    variable: str  # explicit, never inferred
    variables: dict[str, DivinerVariable] | None = None
    units_override: str | None = None


def decode(label_path: Path, params: DivinerDecodeParams) -> DecodedRaster:
    variable = variable_for(params.variable, params.variables)
    if variable is None:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT",
            f"Diviner variable {params.variable!r} is not supported",
            detail_code="UNSUPPORTED_FORMAT",
        )
    image = read_image(label_path)
    check_body_and_frame(image, "MOON")
    affine, domain, dx, _ = geometry(image)
    unit = params.units_override or image.unit
    values = image.values.copy()
    notes = [
        f"Scale {image.scale:g} and offset {image.offset:g} from the label were applied exactly once.",
        f"Variable {variable.name} ({variable.aggregation}); the time/local-time support is the product's "
        "documented aggregation window and is not comparable to an Earth air temperature.",
    ]
    if unit is not None and unit.strip().lower() in _CELSIUS:
        values = values + 273.15
        notes.append("Label unit was Celsius; converted to kelvin by +273.15.")
    elif not is_kelvin(unit):
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"cannot interpret thermal unit {unit!r} as kelvin", detail_code="UNSUPPORTED_FORMAT"
        )
    physical = np.isfinite(values) & (values > 0.0)
    valid = image.valid & physical
    if int((image.valid & ~physical).sum()):
        notes.append(f"{int((image.valid & ~physical).sum())} non-physical (<= 0 K) sample(s) masked invalid.")
    data = np.where(valid, values, np.nan)
    radius = image.a_radius_m or MOON_RADIUS_M
    meta = RasterMetadata(
        adapter_id=DIVINER_ADAPTER_ID,
        body="MOON",
        quantity=f"temperature_{variable.aggregation}",
        units="K",
        vertical_reference=None,
        crs_wkt=geographic_wkt("Moon", radius),
        transform=affine,
        width=values.shape[1],
        height=values.shape[0],
        pixel_registration="PIXEL_EDGE_BOUNDS_FROM_LABEL",
        longitude_domain=domain,
        source_scale=image.scale,
        source_offset=image.offset,
        scale_applied=True,
        nodata_raw=image.missing_raw[0] if image.missing_raw else None,
        product_id=image.product_id,
        notes=tuple(notes),
        attributes={
            **image.attributes,
            "variable": variable.name,
            "aggregation": variable.aggregation,
            "pixel_size_deg": f"{dx:.12g}",
        },
    )
    return DecodedRaster(data=data, valid=valid, metadata=meta)
