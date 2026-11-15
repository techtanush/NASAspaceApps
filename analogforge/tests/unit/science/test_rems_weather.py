"""Real public PDS byte controls, quality masks, body/time and mode limitations."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from analogforge.adapters.rems import fetch_rems_weather, parse_rems_weather

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "real" / "rems"
NAME = "RME_397535244RMD00010000000_______PA"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


@pytest.fixture
def product():
    return (ROOT / (NAME + ".xml")).read_bytes(), (ROOT / (NAME + ".TAB")).read_bytes()


def test_original_public_product_checksums_and_raw_controls(product):
    label, table = product
    assert hashlib.sha256(label).hexdigest() == "ce4d63f2be20f8d55d4a2ffaea8a5fedc2338f134243b96396af7af39c123af9"
    assert hashlib.sha256(table).hexdigest() == "e38f69846b30e84c13d6bc916b04e2ff27a782172c35bc025faca65740f3669f"
    expected = [(1, -999, "XXXX", -999, "-999.00"), (241, 293.45, "0111", -999, "-999.00"),
                (301, 228.98, "0111", -999, "-999.00"), (401, 292.58, "1111", -999, "-999.00"),
                (750, 237.17, "0111", 702.91, "11")]
    for number, temp, flags, pressure, ps_flags in expected:
        row = table[(number - 1) * 372:number * 372]
        assert float(row[84:91]) == temp and row[109:117].decode().strip() == flags
        assert float(row[344:351]) == pressure and row[361:369].decode().strip() == ps_flags


def test_real_product_decoder_preserves_quality_and_unknown_geography(product):
    result = parse_rems_weather(*product, sol=1, fetched_at=NOW)
    assert result["status"] == "LIMITED" and result["body"] == "MARS"
    assert result["observed_start"] == "2012-08-07T04:04:38.536Z"
    assert result["observed_end"] == "2012-08-07T04:24:19.547Z"
    assert result["provenance"]["product_created_at"] == "2015-06-27T07:12:55.205Z"
    assert result["geographic_coordinates"] is None and result["selected_aoi_applicability"] == "UNKNOWN"
    assert result["qualification_supported"] is False
    assert len(result["samples"]) == 24
    first, last = result["samples"][0], result["samples"][-1]
    assert first["values"]["surface_brightness_temperature"]["value"] is None
    assert last["values"]["surface_brightness_temperature"] == {
        "value": 237.17, "unit": "K", "quality_flags": "0111", "quality_accepted": False}
    assert last["values"]["atmospheric_pressure"] == {
        "value": 702.91, "unit": "Pa", "quality_flags": "11", "quality_accepted": True}
    assert last["spacecraft_clock"] == "397585328" and last["valid_at_utc"] is None
    metrics = {m["quantity"]: m for m in result["quantities"]}
    assert metrics["air_temperature"]["minimum"] is None
    assert metrics["air_temperature"]["flagged_sample_count"] == 510
    assert metrics["horizontal_wind_speed"]["missing_sample_count"] == 750
    assert metrics["atmospheric_pressure"]["accepted_sample_count"] == 390


@pytest.mark.parametrize("defect", ["table_truncated", "wrong_product", "wrong_units", "xml_entity", "wrong_sol",
                                    "reversed_time"])
def test_source_metadata_defects_are_unknown(product, defect):
    label, table = product
    sol = 1
    if defect == "table_truncated":
        table = table[:-1]
    elif defect == "wrong_product":
        label = label.replace(NAME.lower().encode(), b"other-product")
    elif defect == "wrong_units":
        label = label.replace(b">KELVIN<", b">CELSIUS<")
    elif defect == "xml_entity":
        label = b'<!DOCTYPE doc [<!ENTITY bad "bad">]>' + label
    elif defect == "reversed_time":
        label = label.replace(b"2012-08-07T04:24:19.547Z", b"2011-08-07T04:24:19.547Z")
    else:
        sol = 10
    result = parse_rems_weather(label, table, sol=sol, fetched_at=NOW)
    assert result["status"] == "UNKNOWN" and result["reason_code"] == "SOURCE_CONTENT_INVALID"


def test_mock_fetch_loads_only_registered_archive_and_never_falls_back_on_replay(product):
    seen = []
    def mock(request):
        seen.append(str(request.url))
        assert request.url.host == "pds-atmospheres.nmsu.edu"
        assert "authorization" not in request.headers
        return httpx.Response(200, content=product[0 if request.url.path.endswith(".xml") else 1])
    with httpx.Client(transport=httpx.MockTransport(mock), auth=("other-provider", "dummy")) as client:
        result = fetch_rems_weather(client=client, sol=1, fetched_at=NOW)
        assert result["status"] == "LIMITED" and len(seen) == 2
        assert fetch_rems_weather(client=client, sol=1, mode="replay")["status"] == "UNKNOWN"
        assert fetch_rems_weather(client=client, sol=9999)["reason_code"] == "PRODUCT_NOT_REGISTERED"
        assert len(seen) == 2
