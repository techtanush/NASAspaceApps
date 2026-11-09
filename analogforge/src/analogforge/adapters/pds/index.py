"""PDS3 index-table discovery (label-described fixed-width table) with deterministic ordering and a cap."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pvl
from pvl.collections import Quantity

from analogforge.adapters.source_http.client import SafeHttp
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.geo import Box, coverage_fraction, split_bbox
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import CoverageSelection, ResolveCoverageInput

_SAFE_REL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


@dataclass(frozen=True)
class IndexColumns:
    file: str = "FILE_SPECIFICATION_NAME"
    min_lat: str = "MINIMUM_LATITUDE"
    max_lat: str = "MAXIMUM_LATITUDE"
    west: str = "WESTERNMOST_LONGITUDE"
    east: str = "EASTERNMOST_LONGITUDE"


@dataclass(frozen=True)
class PdsSource:
    """A maintained PDS archive location. URLs are configuration proposals, never validated against a live server."""

    adapter_id: str
    body: str  # MARS | MOON
    product_id: str
    version: str | None
    host: str
    index_label_url: str
    base_url: str  # product ids from the index are appended to this
    longitude_domain: str  # domain the index uses: NEG180_180 | ZERO_360
    native_resolution_m: float | None = None
    columns: IndexColumns = IndexColumns()


@dataclass(frozen=True)
class IndexEntry:
    path: str
    box: Box


def validate_relative(path: str) -> str:
    if not _SAFE_REL.match(path) or ".." in path.split("/") or "//" in path:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"unsafe product path {path!r}",
                   detail_code="ARCHIVE_PATH_TRAVERSAL")
    return path


def _num(value: Any) -> float | None:
    if isinstance(value, Quantity):
        value = value.value
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def parse_index(label_text: str, table_text: str, columns: IndexColumns) -> list[IndexEntry]:
    """Parse a PDS3 INDEX_TABLE described by ``label_text``; every row is validated against the label."""
    try:
        label = pvl.loads(label_text)
    except Exception as exc:  # noqa: BLE001 - any parser error means the index label is unusable
        raise AdapterError("SOURCE_CONTENT_INVALID", "index label could not be parsed",
                           detail_code="LABEL_PARSE_ERROR") from exc
    table = label.get("INDEX_TABLE") or label.get("TABLE")
    if table is None:
        raise AdapterError("UNSUPPORTED_PRODUCT", "index label has no INDEX_TABLE object",
                   detail_code="UNSUPPORTED_FORMAT")
    rows = _num(table.get("ROWS"))
    row_bytes = _num(table.get("ROW_BYTES"))
    if rows is None or row_bytes is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "index label lacks ROWS/ROW_BYTES",
                   detail_code="METADATA_INCOMPLETE")
    spans: dict[str, tuple[int, int]] = {}
    for key, value in table.items():
        if key == "COLUMN" and hasattr(value, "get"):
            name = value.get("NAME")
            start = _num(value.get("START_BYTE"))
            width = _num(value.get("BYTES"))
            if isinstance(name, str) and start is not None and width is not None:
                spans[name] = (int(start) - 1, int(start) - 1 + int(width))
    needed = (columns.file, columns.min_lat, columns.max_lat, columns.west, columns.east)
    missing = [c for c in needed if c not in spans]
    if missing:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"index table lacks columns {missing}",
                   detail_code="METADATA_INCOMPLETE")
    lines = [ln for ln in table_text.splitlines() if ln.strip()]
    if len(lines) != int(rows):
        raise AdapterError("SOURCE_CONTENT_INVALID", f"index table has {len(lines)} rows, label declares {int(rows)}",
                           detail_code="SHAPE_MISMATCH")
    entries: list[IndexEntry] = []
    for line in lines:
        if len(line.rstrip("\r\n")) < max(end for _, end in spans.values()):
            raise AdapterError("SOURCE_CONTENT_INVALID", "index row shorter than its columns",
                       detail_code="SHAPE_MISMATCH")

        def cell(name: str, row: str = line) -> str:
            a, b = spans[name]
            return row[a:b].strip().strip('"').strip()

        try:
            south, north = float(cell(columns.min_lat)), float(cell(columns.max_lat))
            west, east = float(cell(columns.west)), float(cell(columns.east))
        except ValueError as exc:
            raise AdapterError("SOURCE_CONTENT_INVALID", "index row has non-numeric bounds",
                               detail_code="METADATA_INCOMPLETE") from exc
        entries.append(IndexEntry(validate_relative(cell(columns.file)), (west, south, east, north)))
    return entries


def _pieces_for(box: Box) -> list[Box]:
    west, south, east, north = box
    if east < west:  # row wraps its own seam
        return [(west, south, 360.0, north), (0.0, south, east, north)]
    return [box]


def discover_in_index(http: SafeHttp, source: PdsSource, request: ResolveCoverageInput, *,
                      max_products: int = 100, extra_notes: tuple[str, ...] = ()) -> list[CoverageSelection]:
    label_bytes = http.get_bytes(source.index_label_url)
    label_text = label_bytes.content.decode("utf-8", errors="replace")
    try:
        parsed = pvl.loads(label_text)
    except Exception as exc:  # noqa: BLE001 - any parser error means the index label is unusable
        raise AdapterError("SOURCE_CONTENT_INVALID", "index label could not be parsed",
                           detail_code="LABEL_PARSE_ERROR") from exc
    pointer = parsed.get("^INDEX_TABLE") or parsed.get("^TABLE")
    if isinstance(pointer, (list, tuple)):
        pointer = pointer[0] if pointer else None
    if not isinstance(pointer, str):
        raise AdapterError("SOURCE_CONTENT_INVALID", "index label has no table pointer",
                   detail_code="METADATA_INCOMPLETE")
    table_url = source.index_label_url.rsplit("/", 1)[0] + "/" + validate_relative(pointer)
    table = http.get_bytes(table_url)
    entries = parse_index(label_text, table.content.decode("utf-8", errors="replace"), source.columns)
    aoi_pieces = split_bbox(request.aoi.bbox, request.aoi.longitude_convention, source.longitude_domain)
    hits: list[IndexEntry] = []
    for entry in sorted(entries, key=lambda e: e.path):
        pieces = _pieces_for(entry.box)
        if any(cov > 0 for cov in (coverage_fraction(aoi_pieces, [p]) for p in pieces)):
            hits.append(entry)
    key_base = {"bbox": list(request.aoi.bbox), "adapter": source.adapter_id}
    if not hits:
        return [CoverageSelection(
            selection_key=f"{source.adapter_id}:{canonical_sha256({**key_base, 'ids': []})[:16]}",
            adapter_id=source.adapter_id, product_id=source.product_id, version=source.version, granule_ids=[],
            access_state="NO_COVERAGE", coverage_fraction=0.0, native_resolution_m=source.native_resolution_m,
            notes=["no indexed product intersects the AOI (NO_GRANULES)", *extra_notes])]
    capped = hits[:max_products]
    fraction = coverage_fraction(aoi_pieces, [b for e in capped for b in _pieces_for(e.box)])
    notes = [f"{len(capped)} product(s) matched; coverage_fraction is planar-degree footprint overlap.", *extra_notes]
    if len(hits) > len(capped):
        notes.append(f"DISCOVERY_TRUNCATED: results capped at {len(capped)} of {len(hits)} matching products; "
                     "coverage_fraction is a lower bound.")
    ids = [e.path for e in capped]
    return [CoverageSelection(
        selection_key=f"{source.adapter_id}:{canonical_sha256({**key_base, 'ids': ids})[:16]}",
        adapter_id=source.adapter_id, product_id=source.product_id, version=source.version, granule_ids=ids,
        access_state="AVAILABLE", coverage_fraction=fraction, native_resolution_m=source.native_resolution_m,
        notes=notes)]
