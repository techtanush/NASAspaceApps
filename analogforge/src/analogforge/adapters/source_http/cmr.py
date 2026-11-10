"""CMR-style granule discovery and fetch shared by the Earthdata-family adapters.

The response shapes parsed here (``granules.umm_json`` items, ``CMR-Hits`` / ``CMR-Search-After`` headers)
are format-faithful to the published CMR API and are exercised only against ``httpx.MockTransport``;
nothing in this module has been validated against a live CMR.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from analogforge.adapters.source_http.client import ExpectedChecksum, SafeHttp, has_credentials, redact_url
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.geo import Box, coverage_fraction, split_bbox, to_cmr_bounding_boxes
from analogforge.adapters.source_http.policy import HttpPolicy
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 4
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_NAME_LENGTH = 200


@dataclass(frozen=True)
class CmrDownload:
    url: str
    name: str
    size_bytes: int | None
    checksum: ExpectedChecksum | None


@dataclass(frozen=True)
class CmrGranule:
    concept_id: str
    granule_ur: str
    boxes: tuple[Box, ...]
    downloads: tuple[CmrDownload, ...]


@dataclass(frozen=True)
class CmrSearchResult:
    granules: tuple[CmrGranule, ...]
    hits: int | None
    truncated: bool
    pages: int


def _checksum(entry: dict[str, Any]) -> ExpectedChecksum | None:
    info = entry.get("Checksum")
    if not isinstance(info, dict):
        return None
    algo = str(info.get("Algorithm", "")).lower().replace("-", "")
    value = info.get("Value")
    if algo in {"sha256", "md5"} and isinstance(value, str) and value:
        return ExpectedChecksum(algo, value.lower())
    return None


def parse_umm_item(item: dict[str, Any]) -> CmrGranule:
    meta = item.get("meta") or {}
    umm = item.get("umm") or {}
    concept = meta.get("concept-id")
    ur = umm.get("GranuleUR")
    if not isinstance(concept, str) or not isinstance(ur, str):
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", "CMR item lacks concept-id or GranuleUR", detail_code="METADATA_INCOMPLETE"
        )
    boxes: list[Box] = []
    geometry = ((umm.get("SpatialExtent") or {}).get("HorizontalSpatialDomain") or {}).get("Geometry") or {}
    for rect in geometry.get("BoundingRectangles") or []:
        try:
            boxes.append(
                (
                    float(rect["WestBoundingCoordinate"]),
                    float(rect["SouthBoundingCoordinate"]),
                    float(rect["EastBoundingCoordinate"]),
                    float(rect["NorthBoundingCoordinate"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID",
                f"granule {ur} has a malformed bounding rectangle",
                detail_code="METADATA_INCOMPLETE",
            ) from exc
    by_name: dict[str, dict[str, Any]] = {}
    arch = (umm.get("DataGranule") or {}).get("ArchiveAndDistributionInformation") or []
    for entry in arch:
        if isinstance(entry, dict) and isinstance(entry.get("Name"), str):
            by_name[entry["Name"]] = entry
    downloads: list[CmrDownload] = []
    for related in umm.get("RelatedUrls") or []:
        if not isinstance(related, dict) or related.get("Type") != "GET DATA":
            continue
        url = related.get("URL")
        if not isinstance(url, str) or urlsplit(url).scheme != "https":
            continue
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        entry = by_name.get(name, {})
        size = entry.get("SizeInBytes")
        downloads.append(
            CmrDownload(url, name, int(size) if isinstance(size, int) and size >= 0 else None, _checksum(entry))
        )
    return CmrGranule(concept, ur, tuple(boxes), tuple(sorted(downloads, key=lambda d: d.url)))


def search_granules(
    http: SafeHttp,
    *,
    short_name: str,
    version: str,
    bounding_boxes: Sequence[str],
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    base_url: str = CMR_GRANULES_URL,
) -> CmrSearchResult:
    """Search granules for each bounding box; merge, de-duplicate, sort deterministically, cap and disclose."""
    found: dict[str, CmrGranule] = {}
    hits_total = 0
    hits_known = True
    pages = 0
    truncated = False
    for bounding_box in bounding_boxes:
        search_after: str | None = None
        collected_here = 0
        hits_here: int | None = None
        for _ in range(max_pages):
            params: dict[str, Any] = {
                "short_name": short_name,
                "version": version,
                "bounding_box": bounding_box,
                "page_size": page_size,
                "sort_key[]": "producer_granule_id",
            }
            headers = {"CMR-Search-After": search_after} if search_after else None
            payload, response_headers = http.get_json(base_url, params=params, headers=headers)
            pages += 1
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                raise AdapterError(
                    "SOURCE_CONTENT_INVALID", "CMR response has no items list", detail_code="METADATA_INCOMPLETE"
                )
            for item in items:
                granule = parse_umm_item(item)
                found.setdefault(granule.concept_id, granule)
            collected_here += len(items)
            raw_hits = response_headers.get("cmr-hits")
            if raw_hits is not None and raw_hits.isdigit():
                hits_here = int(raw_hits)
            search_after = response_headers.get("cmr-search-after")
            if len(items) < page_size or not search_after:
                break
            if hits_here is not None and collected_here >= hits_here:
                break
        else:
            truncated = True  # page cap reached while the provider still signalled more pages
        if hits_here is None:
            hits_known = False
        else:
            hits_total += hits_here
            if collected_here < hits_here:
                truncated = True
    ordered = tuple(sorted(found.values(), key=lambda g: (g.granule_ur, g.concept_id)))
    return CmrSearchResult(ordered, hits_total if hits_known else None, truncated, pages)


def lookup_granule(http: SafeHttp, concept_id: str, base_url: str = CMR_GRANULES_URL) -> CmrGranule:
    payload, _ = http.get_json(base_url, params={"concept_id": concept_id})
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise AdapterError("NO_COVERAGE", f"granule {concept_id} not found in CMR", detail_code="NO_GRANULES")
    granule = parse_umm_item(items[0])
    if granule.concept_id != concept_id:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", "CMR returned a different granule than requested", detail_code="GRANULE_MISMATCH"
        )
    return granule


def asset_directory(scratch: Path, adapter_id: str, granule_ur: str) -> Path:
    """Deterministic, traversal-free location of one granule's bytes under ``scratch``."""
    name = _SAFE_NAME.sub("_", granule_ur)
    if not name.strip(".") or len(name) > _MAX_NAME_LENGTH:  # "", ".", "..", "..." or an unusable length
        raise AdapterError("SOURCE_CONTENT_INVALID", "unusable granule name", detail_code="PATH_ESCAPE")
    path = scratch / "source_bytes" / adapter_id / name
    resolved = path.resolve()
    if (scratch / "source_bytes" / adapter_id).resolve() != resolved.parent:
        raise AdapterError("SOURCE_CONTENT_INVALID", "scratch path escape", detail_code="PATH_ESCAPE")
    return path


def fetch_cmr_assets(
    http: SafeHttp,
    selection: CoverageSelection,
    scratch: Path,
    *,
    adapter_id: str,
    product_id: str,
    suffixes: tuple[str, ...],
    accept_content_types: tuple[str, ...] | None,
    expected_magic: bytes | None,
    max_bytes: int | None = None,
) -> list[AcquiredAsset]:
    """Resolve each selected granule's download through CMR (never an agent-supplied URL) and fetch it."""
    if selection.adapter_id != adapter_id:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT",
            f"selection belongs to {selection.adapter_id}, not {adapter_id}",
            detail_code="ADAPTER_MISMATCH",
        )
    if selection.access_state == "NO_COVERAGE":
        raise AdapterError("NO_COVERAGE", "selection has no coverage", detail_code="NO_GRANULES")
    if selection.access_state == "UNSUPPORTED":
        raise AdapterError("UNSUPPORTED_PRODUCT", "selection is unsupported", detail_code="UNSUPPORTED_FORMAT")
    if not http.has_credentials:
        raise AdapterError(
            "PROVIDER_AUTH_FAILED",
            "Earthdata credentials are required to download granules",
            detail_code="AUTH_REQUIRED",
        )
    if not selection.granule_ids:
        raise AdapterError("NO_COVERAGE", "selection lists no granules", detail_code="NO_GRANULES")
    assets: list[AcquiredAsset] = []
    for concept_id in sorted(selection.granule_ids):
        granule = lookup_granule(http, concept_id)
        candidates = [d for d in granule.downloads if d.name.lower().endswith(suffixes)]
        if not candidates:
            raise AdapterError(
                "UNSUPPORTED_PRODUCT",
                f"granule {granule.granule_ur} has no {'/'.join(suffixes)} file",
                detail_code="UNSUPPORTED_FORMAT",
            )
        chosen = candidates[0]
        directory = asset_directory(scratch, adapter_id, granule.granule_ur)
        result = http.download(
            chosen.url,
            directory / chosen.name,
            expected=chosen.checksum,
            max_bytes=max_bytes,
            accept_content_types=accept_content_types,
            expected_magic=expected_magic,
        )
        if chosen.size_bytes is not None and chosen.size_bytes != result.size_bytes:
            result.path.unlink(missing_ok=True)
            raise AdapterError(
                "SOURCE_CONTENT_INVALID",
                f"size {result.size_bytes} differs from provider-declared {chosen.size_bytes}",
                detail_code="SIZE_MISMATCH",
            )
        assets.append(
            AcquiredAsset(
                adapter_id=adapter_id,
                product_id=product_id,
                version=selection.version,
                granule_id=concept_id,
                source_uri=redact_url(chosen.url),
                sha256=result.sha256,
                size_bytes=result.size_bytes,
                validation_status="VERIFIED" if result.provider_checksum_verified else "PENDING",
                artifact_key=f"source-bytes:{adapter_id}:{granule.granule_ur}",
            )
        )
    return assets


def selection_key(adapter_id: str, bbox: Sequence[float], ids: Sequence[str]) -> str:
    return f"{adapter_id}:{canonical_sha256({'bbox': list(bbox), 'ids': list(ids)})[:16]}"


def empty_selection(
    adapter_id: str,
    product_id: str | None,
    version: str | None,
    request: ResolveCoverageInput,
    state: str,
    note: str,
    native_resolution_m: float | None,
) -> CoverageSelection:
    return CoverageSelection.model_validate(
        {
            "selection_key": selection_key(adapter_id, request.aoi.bbox, []),
            "adapter_id": adapter_id,
            "product_id": product_id,
            "version": version,
            "granule_ids": [],
            "access_state": state,
            "coverage_fraction": 0.0 if state == "NO_COVERAGE" else None,
            "native_resolution_m": native_resolution_m,
            "notes": [note],
        }
    )


def discover_cmr_selection(
    client: httpx.Client | None,
    policy: HttpPolicy,
    request: ResolveCoverageInput,
    *,
    adapter_id: str,
    short_name: str,
    version: str,
    product_id: str,
    native_resolution_m: float | None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> CoverageSelection:
    """One deterministic selection for the AOI. Metadata search is public; ``AUTH_REQUIRED`` is reported when the
    injected client carries no credential (downloads need one). Truncation by the page cap is disclosed."""
    if client is None:
        return empty_selection(
            adapter_id,
            product_id,
            version,
            request,
            "UNAVAILABLE",
            "no HTTP client supplied (offline mode)",
            native_resolution_m,
        )
    http = SafeHttp(client, policy)
    result = search_granules(
        http,
        short_name=short_name,
        version=version,
        page_size=page_size,
        max_pages=max_pages,
        bounding_boxes=to_cmr_bounding_boxes(request.aoi.bbox, request.aoi.longitude_convention),
    )
    if not result.granules:
        return empty_selection(
            adapter_id,
            product_id,
            version,
            request,
            "NO_COVERAGE",
            "no granules intersect the AOI (NO_GRANULES)",
            native_resolution_m,
        )
    ids = [g.concept_id for g in result.granules]
    pieces = split_bbox(request.aoi.bbox, request.aoi.longitude_convention, "NEG180_180")
    notes = [
        f"{len(ids)} granule(s) found; coverage_fraction is planar-degree footprint overlap, not valid-pixel coverage."
    ]
    if result.truncated:
        total = result.hits if result.hits is not None else "unknown"
        notes.append(
            f"DISCOVERY_TRUNCATED: results capped at {len(ids)} of {total} granules; "
            "coverage_fraction is a lower bound."
        )
    state = "AVAILABLE" if has_credentials(client) else "AUTH_REQUIRED"
    if state == "AUTH_REQUIRED":
        notes.append("File download requires an Earthdata Login credential supplied through the HTTP client.")
    return CoverageSelection.model_validate(
        {
            "selection_key": selection_key(adapter_id, request.aoi.bbox, ids),
            "adapter_id": adapter_id,
            "product_id": product_id,
            "version": version,
            "granule_ids": ids,
            "access_state": state,
            "coverage_fraction": coverage_fraction(pieces, [b for g in result.granules for b in g.boxes]),
            "native_resolution_m": native_resolution_m,
            "notes": notes,
        }
    )
