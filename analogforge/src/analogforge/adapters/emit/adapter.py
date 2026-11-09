"""EMIT L2B mineral adapter: CMR discovery, NetCDF fetch, decode (see :mod:`analogforge.adapters.emit.decode`)."""

from __future__ import annotations

from pathlib import Path

import httpx

from analogforge.adapters.emit import decode as emit_decode
from analogforge.adapters.source_http.client import SafeHttp
from analogforge.adapters.source_http.cmr import (
    asset_directory,
    discover_cmr_selection,
    empty_selection,
    fetch_cmr_assets,
)
from analogforge.adapters.source_http.decoded import DecodedRaster
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.policy import HttpPolicy
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

EMIT_ADAPTER_ID = "earth_emit_l2bmin_v001"
SHORT_NAME = "EMITL2BMIN"
VERSION = "001"
NATIVE_RESOLUTION_M = 60.0
SUPPORTED_KINDS = frozenset({"mineral_id", "mineral", "band_depth", "mineral_uncertainty"})
DEFAULT_ALLOWED_HOSTS = frozenset({"cmr.earthdata.nasa.gov", "data.lpdaac.earthdatacloud.nasa.gov",
                                   "urs.earthdata.nasa.gov"})
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"


def default_policy() -> HttpPolicy:
    return HttpPolicy(allowed_hosts=DEFAULT_ALLOWED_HOSTS, auth_hosts=frozenset({"urs.earthdata.nasa.gov"}))


def discover(request: ResolveCoverageInput, client: httpx.Client | None, *, policy: HttpPolicy | None = None,
             page_size: int = 50, max_pages: int = 4) -> list[CoverageSelection]:
    if request.adapter_id != EMIT_ADAPTER_ID:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"unknown adapter {request.adapter_id!r}",
                           detail_code="UNSUPPORTED_FORMAT")
    if request.aoi.body != "EARTH":
        raise AdapterError("UNSUPPORTED_PRODUCT", f"EMIT is an Earth product; AOI body is {request.aoi.body}",
                           detail_code="BODY_MISMATCH")
    unknown = sorted(set(request.measurement_kinds) - SUPPORTED_KINDS)
    if unknown or not request.measurement_kinds:
        return [empty_selection(EMIT_ADAPTER_ID, SHORT_NAME, VERSION, request, "UNSUPPORTED",
                                f"measurement kinds not provided by EMIT L2B MIN: {unknown or 'none requested'}",
                                NATIVE_RESOLUTION_M)]
    selection = discover_cmr_selection(client, policy or default_policy(), request, adapter_id=EMIT_ADAPTER_ID,
                                       short_name=SHORT_NAME, version=VERSION, product_id=SHORT_NAME,
                                       native_resolution_m=NATIVE_RESOLUTION_M, page_size=page_size,
                                       max_pages=max_pages)
    note = ("Granule footprint overlap proves only swath intersection; valid mineral-retrieval area must be "
            "computed after decode with the product masks.")
    return [selection.model_copy(update={"notes": [*selection.notes, note]})] if selection.granule_ids else [selection]


def fetch(selection: CoverageSelection, client: httpx.Client | None, scratch: Path, *,
          policy: HttpPolicy | None = None, max_bytes: int | None = None) -> list[AcquiredAsset]:
    if client is None:
        raise AdapterError("PROVIDER_AUTH_FAILED", "no HTTP client with credentials supplied",
                           detail_code="AUTH_REQUIRED")
    http = SafeHttp(client, policy or default_policy())
    return fetch_cmr_assets(http, selection, scratch, adapter_id=EMIT_ADAPTER_ID, product_id=SHORT_NAME,
                            suffixes=(".nc",), accept_content_types=None, expected_magic=HDF5_MAGIC,
                            max_bytes=max_bytes)


def asset_path(scratch: Path, asset: AcquiredAsset) -> Path:
    granule_ur = asset.artifact_key.split(":", 2)[2]
    return asset_directory(scratch, asset.adapter_id, granule_ur) / asset.source_uri.rsplit("/", 1)[-1]


def decode(path: Path, params: emit_decode.EmitDecodeParams | None = None) -> DecodedRaster:
    return emit_decode.decode(path, params)
