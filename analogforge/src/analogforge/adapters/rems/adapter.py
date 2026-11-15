"""Bounded real REMS MODRDR loading, preserving station/time/quality limits.

Only the two inspected archive products below are selectable. Their PDS4 labels
provide fixed-width field locations and units. No terrestrial weather service,
SCLK-to-UTC guess, or geographic interpolation is used.
"""

from __future__ import annotations

import hashlib
import math
import re
import xml.etree.ElementTree as ET  # noqa: S405 - DTD/entity declarations rejected before parsing
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from analogforge.adapters.meteomatics.adapter import iso
from analogforge.adapters.pds.xml_safe import find_all, text_of

BASE_URL = "https://pds-atmospheres.nmsu.edu/PDS/data/mslrem_1001/"
PRODUCTS = {
    1: "DATA/SOL_00001_00089/SOL00001/RME_397535244RMD00010000000_______PA",
    10: "DATA/SOL_00001_00089/SOL00010/RME_398334213RMD00100000000_______PA",
}
QUANTITIES = {
    "AMBIENT_TEMP": ("air_temperature", "KELVIN", "K", "AMBIENT_TEMP_CONFIDENCE_LEVEL"),
    "BRIGHTNESS_TEMP": ("surface_brightness_temperature", "KELVIN", "K", "GTS_CONFIDENCE_LEVEL"),
    "PRESSURE": ("atmospheric_pressure", "PASCAL", "Pa", "PS_CONFIDENCE_LEVEL"),
    "HORIZONTAL_WIND_SPEED": ("horizontal_wind_speed", "METERS/SECOND", "m/s", "WS_CONFIDENCE_LEVEL"),
}
MAX_LABEL_BYTES = 128 * 1024
MAX_TABLE_BYTES = 12 * 1024 * 1024
FLAG_LENGTHS = {"AMBIENT_TEMP": 9, "BRIGHTNESS_TEMP": 4, "PRESSURE": 2, "HORIZONTAL_WIND_SPEED": 6}
LIMITATIONS = [
    "Historical Curiosity rover-point observations in Gale crater; not current or global Mars weather.",
    "Exact planetary geographic coordinates and selected-AOI applicability are unresolved by this product.",
    "Only all-good (all 1) sensor flags contribute to summary ranges; missing, bad and unknown flags remain excluded.",
    "TIMESTAMP is spacecraft clock. Per-row UTC is unknown without the appropriate SPICE clock conversion.",
    "Air temperature and surface brightness temperature are separate quantities; "
    "no Earth/Mars equivalence is inferred.",
    "The selected sample window need not represent a full sol, season, local climate or all conditions at the site.",
    "Summary ranges are nominal accepted samples; "
    "source uncertainty fields have not been summarized or calibrated here.",
]


@dataclass
class _Summary:
    values: list[float] = field(default_factory=list)
    missing: int = 0
    flagged: int = 0


def _unknown(reason: str, mode: str, sol: int, fetched_at: datetime) -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason_code": reason, "body": "MARS", "station_id": "msl-curiosity-rems",
            "sol": sol, "mode": mode, "fetched_at": iso(fetched_at), "quantities": [], "samples": [],
            "scope": "historical_rover_point_context", "selected_aoi_applicability": "UNKNOWN",
            "qualification_supported": False, "limitations": list(LIMITATIONS)}


def _number(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) and value != -999 else None


def parse_rems_weather(
    label_bytes: bytes, table_bytes: bytes, *, sol: int, fetched_at: datetime, mode: str = "live",
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Decode inspected PDS4 MODRDR layouts using the label's field positions.

    Summary coverage denominators are product records, not the full sol. Samples
    preview at most 24 evenly spaced source rows and retain their original flags.
    Hashes cover full unmodified source bytes, suitable for a source manifest.
    """
    if sol not in PRODUCTS:
        return _unknown("PRODUCT_NOT_REGISTERED", mode, sol, fetched_at)
    if mode not in {"live", "replay"}:
        return _unknown("MODE_UNSUPPORTED", mode, sol, fetched_at)
    if len(label_bytes) > MAX_LABEL_BYTES or len(table_bytes) > MAX_TABLE_BYTES:
        return _unknown("RESOURCE_LIMIT", mode, sol, fetched_at)
    try:
        text = label_bytes.decode("utf-8")
        if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.IGNORECASE):
            raise ValueError("XML declarations not permitted")
        root = ET.fromstring(text)  # noqa: S314 - DTD and entities rejected above
        lid = text_of(root, "logical_identifier") or ""
        expected_name = PRODUCTS[sol].rsplit("/", 1)[-1]
        if not lid.lower().endswith(":" + expected_name.lower()):
            raise ValueError("Wrong registered product")
        if "urn:nasa:pds:msl_rems:data_calibrated:" not in lid:
            raise ValueError("Wrong data collection")
        if text_of(root, "file_name") != expected_name + ".TAB":
            raise ValueError("Wrong table file")
        tables = find_all(root, "Table_Character")
        if len(tables) != 1:
            raise ValueError("One character table required")
        table = tables[0]
        records = int(text_of(table, "records") or "0")
        record_length = int(text_of(table, "record_length") or "0")
        offset = int(text_of(table, "offset") or "0")
        if not 0 < records <= 100_000 or not 0 < record_length <= 4096 or offset != 0:
            raise ValueError("Unsupported table layout")
        if len(table_bytes) != records * record_length:
            raise ValueError("Table byte count differs from label")
        fields = {}
        for field in find_all(table, "Field_Character"):
            name = text_of(field, "name")
            start = int(text_of(field, "field_location") or "0") - 1
            width = int(text_of(field, "field_length") or "0")
            if not name or name in fields or start < 0 or width <= 0 or start + width > record_length:
                raise ValueError("Invalid field layout")
            fields[name] = (start, width, text_of(field, "unit"))
        required = {"TIMESTAMP", "LMST", "LTST"}
        required |= set(QUANTITIES) | {spec[3] for spec in QUANTITIES.values()}
        if not required <= fields.keys():
            raise ValueError("Missing science fields")
        for name, spec in QUANTITIES.items():
            if fields[name][2] != spec[1]:
                raise ValueError("Unsupported source units")
        observed_start = text_of(root, "start_date_time")
        observed_end = text_of(root, "stop_date_time")
        if not observed_start or not observed_end:
            raise ValueError("Missing UTC coverage")
        # Validate timezone-aware label timestamps, preserving fractional precision in output.
        parsed_bounds = []
        for bound in (observed_start, observed_end):
            parsed = datetime.fromisoformat(bound.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Missing source time zone")
            parsed_bounds.append(parsed)
        if parsed_bounds[1] < parsed_bounds[0]:
            raise ValueError("Invalid source time coverage")
        counts = {name: _Summary() for name in QUANTITIES}
        preview_indices = {round(i * (records - 1) / min(23, records - 1))
                           for i in range(min(24, records))} if records > 1 else {0}
        samples = []
        for index in range(records):
            if check_cancelled is not None and index % 256 == 0:
                check_cancelled()
            row = table_bytes[index * record_length:(index + 1) * record_length].decode("ascii")

            def read(name: str, source_row: str = row) -> str:
                start, width, _ = fields[name]
                return source_row[start:start + width].strip().strip('"')

            lmst = read("LMST")
            if not lmst.startswith(f"{sol:05d}M"):
                raise ValueError("Sol label mismatch")
            sample: dict[str, Any] = {"source_row": index + 1, "spacecraft_clock": read("TIMESTAMP"),
                                      "lmst": lmst, "ltst": read("LTST"), "valid_at_utc": None, "values": {}}
            for name, spec in QUANTITIES.items():
                value, flag = _number(read(name)), read(spec[3])
                if value is not None and ((spec[2] in {"K", "Pa"} and value <= 0)
                                          or (spec[2] == "m/s" and value < 0)):
                    value = None
                accepted = value is not None and len(flag) == FLAG_LENGTHS[name] and set(flag) == {"1"}
                entry = counts[name]
                if value is None:
                    entry.missing += 1
                elif accepted:
                    entry.values.append(value)
                else:
                    entry.flagged += 1
                sample["values"][spec[0]] = {"value": value, "unit": spec[2], "quality_flags": flag,
                                            "quality_accepted": accepted}
            if index in preview_indices:
                samples.append(sample)
    except (ET.ParseError, ValueError, KeyError, TypeError, OverflowError):
        return _unknown("SOURCE_CONTENT_INVALID", mode, sol, fetched_at)
    quantities = []
    for name, spec in QUANTITIES.items():
        entry = counts[name]
        values = entry.values
        quantities.append({"quantity": spec[0], "source_field": name, "unit": spec[2],
                           "minimum": min(values) if values else None, "maximum": max(values) if values else None,
                           "accepted_sample_count": len(values), "product_record_count": records,
                           "missing_sample_count": entry.missing, "flagged_sample_count": entry.flagged,
                           "coverage_fraction_of_product_records": len(values) / records})
    path = BASE_URL + PRODUCTS[sol]
    return {"status": "LIMITED", "reason_code": "HISTORICAL_POINT_CONTEXT_ONLY", "body": "MARS",
            "station_id": "msl-curiosity-rems", "station_name": "Curiosity REMS, Gale crater", "sol": sol,
            "mode": mode, "fetched_at": iso(fetched_at), "observed_start": observed_start, "observed_end": observed_end,
            "scope": "historical_rover_point_context", "selected_aoi_applicability": "UNKNOWN",
            "geographic_coordinates": None, "qualification_supported": False, "quantities": quantities,
            "samples": samples, "sample_selection": "At most 24 evenly spaced source rows; summaries use all records.",
            "provenance": {"provider": "NASA PDS Atmospheres", "logical_identifier": lid,
                           "pds4_version": text_of(root, "version_id"), "record_count": records,
                           "product_created_at": text_of(root, "creation_date_time"),
                           "label_url": path + ".xml", "table_url": path + ".TAB",
                           "label_sha256": hashlib.sha256(label_bytes).hexdigest(),
                           "table_sha256": hashlib.sha256(table_bytes).hexdigest(),
                           "label_bytes": len(label_bytes), "table_bytes": len(table_bytes),
                           "archive_doi": "https://doi.org/10.17189/vwva-ms24",
                           "errata_url": BASE_URL + "ERRATA.TXT", "quality_policy": "ALL_FLAG_CHARACTERS_GOOD_V1"},
            "limitations": list(LIMITATIONS)}


def _download(
    client: httpx.Client, url: str, cap: int, timeout: float, check: Callable[[], None] | None,
) -> bytes | None:
    if check is not None:
        check()
    with client.stream("GET", url, auth=None, timeout=timeout, follow_redirects=False) as response:
        if response.status_code != 200:
            return None
        raw = bytearray()
        for block in response.iter_bytes(chunk_size=32768):
            if check is not None:
                check()
            raw.extend(block)
            if len(raw) > cap:
                return None
    return bytes(raw)


def fetch_rems_weather(
    *, client: httpx.Client | None, sol: int = 10, mode: str = "live", fetched_at: datetime | None = None,
    timeout_seconds: float = 30, check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Load one registered historical product (two bounded requests), without credentials."""
    fetched = fetched_at or datetime.now(UTC)
    if sol not in PRODUCTS:
        return _unknown("PRODUCT_NOT_REGISTERED", mode, sol, fetched)
    if mode != "live":
        return _unknown("NETWORK_DISABLED_FOR_MODE", mode, sol, fetched)
    if client is None:
        return _unknown("SOURCE_UNAVAILABLE", mode, sol, fetched)
    path = BASE_URL + PRODUCTS[sol]
    try:
        label = _download(client, path + ".xml", MAX_LABEL_BYTES, timeout_seconds, check_cancelled)
        table = _download(client, path + ".TAB", MAX_TABLE_BYTES, timeout_seconds, check_cancelled) if label else None
    except httpx.HTTPError:
        return _unknown("SOURCE_UNAVAILABLE", mode, sol, fetched)
    if label is None or table is None:
        return _unknown("SOURCE_UNAVAILABLE", mode, sol, fetched)
    result = parse_rems_weather(label, table, sol=sol, fetched_at=fetched, mode=mode, check_cancelled=check_cancelled)
    if check_cancelled is not None:
        check_cancelled()
    return result
