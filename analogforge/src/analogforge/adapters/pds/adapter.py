"""PDS adapters for Mars MOLA (MEGDR) and Moon LOLA (GDR): index discovery, label+image fetch, decode."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx

from analogforge.adapters.pds import decode as pds_decode
from analogforge.adapters.pds import pds3, pds4
from analogforge.adapters.pds.decode import PdsDecodeParams
from analogforge.adapters.pds.index import PdsSource, discover_in_index, validate_relative
from analogforge.adapters.pds.xml_safe import parse_xml_file
from analogforge.adapters.source_http.client import SafeHttp, redact_url
from analogforge.adapters.source_http.decoded import DecodedRaster
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.policy import HttpPolicy
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

MOLA_ADAPTER_ID = "mars_mola_megdr"
LOLA_ADAPTER_ID = "moon_lola_gdr"
PDS_HOST = "pds-geosciences.wustl.edu"
_XML_MAGIC = (b"<?xml", b"\xef\xbb\xbf<?xml")  # PDS4 labels; PDS3 labels and raw images have no single signature

# Unverified configuration proposals (no live server was contacted); override via ``sources=``.
DEFAULT_SOURCES: dict[str, PdsSource] = {
    MOLA_ADAPTER_ID: PdsSource(
        adapter_id=MOLA_ADAPTER_ID,
        body="MARS",
        product_id="MOLA_MEGDR_TOPOGRAPHY",
        version=None,
        host=PDS_HOST,
        index_label_url=f"https://{PDS_HOST}/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/index.lbl",
        base_url=f"https://{PDS_HOST}/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/",
        longitude_domain="ZERO_360",
        native_resolution_m=463.0,
    ),
    LOLA_ADAPTER_ID: PdsSource(
        adapter_id=LOLA_ADAPTER_ID,
        body="MOON",
        product_id="LOLA_GDR",
        version=None,
        host=PDS_HOST,
        index_label_url=f"https://{PDS_HOST}/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/index/index.lbl",
        base_url=f"https://{PDS_HOST}/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/",
        longitude_domain="ZERO_360",
        native_resolution_m=None,
    ),
}


def default_policy() -> HttpPolicy:
    return HttpPolicy(allowed_hosts=frozenset({PDS_HOST}))


def source_for(adapter_id: str, sources: dict[str, PdsSource] | None = None) -> PdsSource:
    source = (sources or DEFAULT_SOURCES).get(adapter_id)
    if source is None:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"unknown PDS adapter {adapter_id!r}", detail_code="UNSUPPORTED_FORMAT"
        )
    return source


def discover(
    request: ResolveCoverageInput,
    client: httpx.Client | None,
    *,
    policy: HttpPolicy | None = None,
    sources: dict[str, PdsSource] | None = None,
    max_products: int = 100,
) -> list[CoverageSelection]:
    source = source_for(request.adapter_id, sources)
    if request.aoi.body != source.body:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT",
            f"{source.product_id} is a {source.body} product; AOI body is {request.aoi.body}",
            detail_code="BODY_MISMATCH",
        )
    if client is None:
        return [
            CoverageSelection(
                selection_key=f"{source.adapter_id}:offline",
                adapter_id=source.adapter_id,
                product_id=source.product_id,
                version=source.version,
                access_state="UNAVAILABLE",
                native_resolution_m=source.native_resolution_m,
                notes=["no HTTP client supplied (offline mode)"],
            )
        ]
    http = SafeHttp(client, policy or replace(default_policy(), allowed_hosts=frozenset({source.host})))
    return discover_in_index(http, source, request, max_products=max_products)


def _data_reference(label_bytes_path: Path) -> str:
    if label_bytes_path.suffix.lower() == ".xml":
        return pds4.data_file_name(parse_xml_file(label_bytes_path))
    return pds3.data_file_name(pds3.load_label(label_bytes_path))


def fetch_pds_products(
    http: SafeHttp, source: PdsSource, selection: CoverageSelection, scratch: Path
) -> list[AcquiredAsset]:
    if selection.adapter_id != source.adapter_id:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"selection belongs to {selection.adapter_id}", detail_code="ADAPTER_MISMATCH"
        )
    if selection.access_state == "NO_COVERAGE" or not selection.granule_ids:
        raise AdapterError("NO_COVERAGE", "selection lists no products", detail_code="NO_GRANULES")
    if selection.access_state == "UNSUPPORTED":
        raise AdapterError("UNSUPPORTED_PRODUCT", "selection is unsupported", detail_code="UNSUPPORTED_FORMAT")
    out: list[AcquiredAsset] = []
    root = (scratch / "source_bytes" / source.adapter_id).resolve()
    for rel in sorted(selection.granule_ids):
        rel = validate_relative(rel)
        label_dest = root / rel
        if root not in label_dest.resolve().parents:
            raise AdapterError("SOURCE_CONTENT_INVALID", "scratch path escape", detail_code="PATH_ESCAPE")
        label_url = source.base_url + rel
        res = http.download(
            label_url,
            label_dest,
            max_bytes=http.policy.max_metadata_bytes,
            expected_magic=_XML_MAGIC if rel.lower().endswith(".xml") else None,
        )
        out.append(_asset(source, selection, rel, res.sha256, res.size_bytes, label_url, role="label"))
        data_name = validate_relative(_data_reference(label_dest))
        data_rel = (rel.rsplit("/", 1)[0] + "/" if "/" in rel else "") + data_name
        data_url = source.base_url + data_rel
        data_res = http.download(data_url, root / data_rel)
        out.append(_asset(source, selection, data_rel, data_res.sha256, data_res.size_bytes, data_url, role="data"))
    return out


def _asset(
    source: PdsSource, selection: CoverageSelection, rel: str, sha256: str, size: int, url: str, *, role: str
) -> AcquiredAsset:
    return AcquiredAsset(
        adapter_id=source.adapter_id,
        product_id=source.product_id,
        version=selection.version,
        granule_id=rel,
        source_uri=redact_url(url),
        sha256=sha256,
        size_bytes=size,
        validation_status="PENDING",  # PDS archives supply no per-file checksum we can compare against here
        artifact_key=f"source-bytes:{source.adapter_id}:{role}:{rel}",
    )


def fetch(
    selection: CoverageSelection,
    client: httpx.Client | None,
    scratch: Path,
    *,
    policy: HttpPolicy | None = None,
    sources: dict[str, PdsSource] | None = None,
) -> list[AcquiredAsset]:
    source = source_for(selection.adapter_id, sources)
    if client is None:
        raise AdapterError("SOURCE_UNAVAILABLE", "no HTTP client supplied", detail_code="OFFLINE")
    http = SafeHttp(client, policy or replace(default_policy(), allowed_hosts=frozenset({source.host})))
    return fetch_pds_products(http, source, selection, scratch)


def asset_path(scratch: Path, asset: AcquiredAsset) -> Path:
    """Local path of a PDS asset (label or data file) under ``scratch``."""
    if asset.granule_id is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "asset has no product path", detail_code="METADATA_INCOMPLETE")
    return scratch / "source_bytes" / asset.adapter_id / validate_relative(asset.granule_id)


def decode(label_path: Path, params: PdsDecodeParams) -> DecodedRaster:
    return pds_decode.decode(label_path, params)
