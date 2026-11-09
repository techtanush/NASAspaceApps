"""Earthdata (CMR + LP DAAC) adapter for NASADEM and the explicit SRTMGL1 alternate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from analogforge.adapters.earthdata import nasadem
from analogforge.adapters.source_http.archive import ArchiveLimits, safe_extract_zip
from analogforge.adapters.source_http.client import SafeHttp
from analogforge.adapters.source_http.cmr import (
    asset_directory,
    discover_cmr_selection,
    empty_selection,
    fetch_cmr_assets,
)
from analogforge.adapters.source_http.decoded import DecodedRaster
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.geo import split_bbox
from analogforge.adapters.source_http.policy import HttpPolicy
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

NASADEM_ADAPTER_ID = "earth_nasadem_hgt_v001"
SRTMGL1_ADAPTER_ID = "earth_srtmgl1_v003"
SUPPORTED_KINDS = frozenset({"elevation", "terrain", "slope", "relief", "water_mask", "source_quality"})
NATIVE_RESOLUTION_M = 30.9  # one arc-second, approximate (angular spacing)
LAT_COVERAGE = (-56.0, 60.0)  # approximate NASADEM/SRTM latitude coverage; exact footprints come from CMR


@dataclass(frozen=True)
class ProductSpec:
    adapter_id: str
    short_name: str
    version: str
    product_id: str


PRODUCTS: dict[str, ProductSpec] = {
    NASADEM_ADAPTER_ID: ProductSpec(NASADEM_ADAPTER_ID, "NASADEM_HGT", "001", "NASADEM_HGT"),
    SRTMGL1_ADAPTER_ID: ProductSpec(SRTMGL1_ADAPTER_ID, "SRTMGL1", "003", "SRTMGL1"),
}

# Host names are configuration proposals taken from public documentation; they are NOT validated against
# live servers. Callers may pass their own HttpPolicy.
DEFAULT_ALLOWED_HOSTS = frozenset({"cmr.earthdata.nasa.gov", "data.lpdaac.earthdatacloud.nasa.gov",
                                   "urs.earthdata.nasa.gov"})
DEFAULT_AUTH_HOSTS = frozenset({"urs.earthdata.nasa.gov"})


def default_policy() -> HttpPolicy:
    return HttpPolicy(allowed_hosts=DEFAULT_ALLOWED_HOSTS, auth_hosts=DEFAULT_AUTH_HOSTS)


def discover(request: ResolveCoverageInput, client: httpx.Client | None, *,
             policy: HttpPolicy | None = None, page_size: int = 50, max_pages: int = 4) -> list[CoverageSelection]:
    """CMR granule discovery. Metadata search is public; ``AUTH_REQUIRED`` flags that download needs a credential."""
    spec = PRODUCTS.get(request.adapter_id)
    if spec is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"unknown Earthdata adapter {request.adapter_id!r}",
                           detail_code="UNSUPPORTED_FORMAT")
    if request.aoi.body != "EARTH":
        raise AdapterError("UNSUPPORTED_PRODUCT", f"{spec.product_id} is an Earth product; AOI body is "
                           f"{request.aoi.body}", detail_code="BODY_MISMATCH")
    unknown = sorted(set(request.measurement_kinds) - SUPPORTED_KINDS)
    if unknown or not request.measurement_kinds:
        return [empty_selection(spec.adapter_id, spec.product_id, spec.version, request, "UNSUPPORTED",
                                f"measurement kinds not provided by {spec.product_id}: {unknown or 'none requested'}",
                                NATIVE_RESOLUTION_M)]
    pieces = split_bbox(request.aoi.bbox, request.aoi.longitude_convention, "NEG180_180")
    if all(n <= LAT_COVERAGE[0] or s >= LAT_COVERAGE[1] for _, s, _, n in pieces):
        return [empty_selection(spec.adapter_id, spec.product_id, spec.version, request, "NO_COVERAGE",
                                "AOI lies outside the approximate 56S-60N NASADEM/SRTM latitude coverage",
                                NATIVE_RESOLUTION_M)]
    return [discover_cmr_selection(client, policy or default_policy(), request, adapter_id=spec.adapter_id,
                                   short_name=spec.short_name, version=spec.version, product_id=spec.product_id,
                                   native_resolution_m=NATIVE_RESOLUTION_M, page_size=page_size,
                                   max_pages=max_pages)]


def fetch(selection: CoverageSelection, client: httpx.Client | None, scratch: Path, *,
          policy: HttpPolicy | None = None, max_bytes: int | None = None) -> list[AcquiredAsset]:
    spec = PRODUCTS.get(selection.adapter_id)
    if spec is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"unknown Earthdata adapter {selection.adapter_id!r}",
                           detail_code="UNSUPPORTED_FORMAT")
    if client is None:
        raise AdapterError("PROVIDER_AUTH_FAILED", "no HTTP client with credentials supplied",
                           detail_code="AUTH_REQUIRED")
    http = SafeHttp(client, policy or default_policy())
    assets = fetch_cmr_assets(http, selection, scratch, adapter_id=spec.adapter_id, product_id=spec.product_id,
                              suffixes=(".zip",), accept_content_types=None,
                              expected_magic=b"PK", max_bytes=max_bytes)
    # Archive safety is verified at fetch time too, so a hostile archive is rejected before any decode.
    for asset in assets:
        archive = _asset_file(scratch, asset)
        safe_extract_zip(archive, archive.with_name(archive.stem + "_check"),
                         ArchiveLimits(max_members=16, allowed_suffixes=nasadem.NASADEM_ARCHIVE_SUFFIXES),
                         extract=False)
    return assets


def _asset_file(scratch: Path, asset: AcquiredAsset) -> Path:
    granule_ur = asset.artifact_key.split(":", 2)[2]
    directory = asset_directory(scratch, asset.adapter_id, granule_ur)
    return directory / asset.source_uri.rsplit("/", 1)[-1]


def asset_path(scratch: Path, asset: AcquiredAsset) -> Path:
    """Local path of an acquired asset's bytes (deterministic from ``scratch`` and the asset)."""
    return _asset_file(scratch, asset)


def decode(path: Path, params: nasadem.NasademParams | None = None) -> DecodedRaster:
    return nasadem.decode(path, params)
