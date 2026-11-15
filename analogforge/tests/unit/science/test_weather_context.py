"""Independent weather parsing, missing-evidence and operating-limit guards."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from analogforge.adapters.meteomatics import WeatherQuery, fetch_earth_weather, parse_weather_response
from analogforge.science.weather import WeatherLimit, compare_operating_weather

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def query(**changes):
    return WeatherQuery(**{"body": "EARTH", "latitude": 35.2, "longitude": -111.6, "start": NOW,
                           "end": NOW + timedelta(hours=1), "parameters": ("t_2m:C",), **changes})


def response(values=(10, 20), **changes):
    return json.dumps({"status": "OK", "dateGenerated": "2026-11-13T23:50:00Z", "user": "private-account",
                       "data": [{"parameter": "t_2m:C", "coordinates": [
                           {"lat": 35.2, "lon": -111.6, "dates": [
                               {"date": "2026-11-14T00:00:00Z", "value": values[0]},
                               {"date": "2026-11-14T01:00:00Z", "value": values[1]}]}]}], **changes}).encode()


def test_weather_provenance_and_explicit_inclusive_limits():
    result = parse_weather_response(query(), response(), fetched_at=NOW)
    assert result.status == "AVAILABLE" and result.coverage_fraction == 1
    assert result.provenance["date_generated"] == "2026-11-13T23:50:00Z"
    assert result.provenance["resolved_model"] is None
    assert "private-account" not in result.artifact_bytes().decode()
    assert "user" not in result.provenance
    check = compare_operating_weather(result, (WeatherLimit("t_2m:C", 10, 20),))
    assert check["status"] == "WITHIN_LIMITS"
    assert check["cross_planet_equivalence"] == "UNKNOWN"
    assert check["qualification_supported"] is False
    assert compare_operating_weather(result, (WeatherLimit("t_2m:C", upper=19),))["status"] == "OUTSIDE_LIMITS"
    assert compare_operating_weather(result, ())["status"] == "UNKNOWN"


@pytest.mark.parametrize("missing", [None, -999, -888, -777, -666, float("nan"), float("inf"), True])
def test_missing_is_unknown_and_never_zero(missing):
    result = parse_weather_response(query(), response((10, missing)), fetched_at=NOW)
    assert result.status == "LIMITED" and result.coverage_fraction == 0.5
    assert result.samples[-1]["value"] is None
    assert compare_operating_weather(result, (WeatherLimit("t_2m:C", upper=20),))["status"] == "UNKNOWN"
    assert compare_operating_weather(result, (WeatherLimit("t_2m:C", upper=9),))["status"] == "OUTSIDE_LIMITS"


@pytest.mark.parametrize("body,mode", [("MARS", "live"), ("MOON", "live"), ("EARTH", "synthetic"),
                                     ("EARTH", "replay")])
def test_no_network_for_planets_or_replay(body, mode):
    def forbidden(request):
        pytest.fail("This body/mode must not call a live provider")
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        result = fetch_earth_weather(
            query(body=body), client=client, username="sample", password="sample", mode=mode,  # noqa: S106 - mock only
        )
    assert result.status == "UNKNOWN"


def test_live_basic_auth_is_not_copied_to_artifact_and_source_is_explicit():
    def mock(request):
        assert request.url.host == "api.meteomatics.com"
        assert request.url.params["source"] == "mix"
        assert request.headers["authorization"].startswith("Basic ")
        assert "sample-secret" not in str(request.url)
        return httpx.Response(200, content=response())
    with httpx.Client(transport=httpx.MockTransport(mock)) as client:
        result = fetch_earth_weather(
            query(), client=client, username="sample-user", password="sample-secret",  # noqa: S106 - mock only
        )
    assert result.status == "AVAILABLE"
    assert "sample-secret" not in repr(result) and "sample-user" not in result.artifact_bytes().decode()


@pytest.mark.parametrize("code", [401, 403, 429, 500, 302])
def test_failure_does_not_leak_provider_error_body(code):
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(code, text="private-account password=sample-secret"))) as client:
        result = fetch_earth_weather(
            query(), client=client, username="sample-user", password="sample-secret",  # noqa: S106 - mock only
        )
    assert result.status == "UNKNOWN" and result.samples == ()
    assert "sample-secret" not in result.artifact_bytes().decode()


def test_replay_explicit_bytes_and_incompatible_parameter_remain_unknown():
    result = parse_weather_response(query(), response(), fetched_at=NOW, mode="replay")
    assert result.mode == "replay" and result.status == "AVAILABLE"
    assert compare_operating_weather(result, (WeatherLimit("wind_speed_10m:ms", upper=5),))["status"] == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["location", "extra_date", "duplicate", "naive_date", "parameter", "nan_location",
                                      "nan_longitude", "fractional_date"])
def test_wrong_series_cannot_qualify_requested_point(mutation):
    raw = json.loads(response())
    series = raw["data"][0]
    point = series["coordinates"][0]
    if mutation == "location":
        point["lat"] = 36
    elif mutation == "nan_location":
        point["lat"] = float("nan")
    elif mutation == "nan_longitude":
        point["lon"] = float("nan")
    elif mutation == "extra_date":
        point["dates"][1]["date"] = "2026-11-15T01:00:00Z"
    elif mutation == "duplicate":
        point["dates"][1]["date"] = point["dates"][0]["date"]
    elif mutation == "naive_date":
        point["dates"][0]["date"] = "2026-11-14T00:00:00"
    elif mutation == "fractional_date":
        point["dates"][0]["date"] = "2026-11-14T00:00:00.900Z"
    else:
        series["parameter"] = "surface_temperature:K"
    assert parse_weather_response(query(), json.dumps(raw).encode(), fetched_at=NOW).status == "UNKNOWN"


@pytest.mark.parametrize("changes", [{"start": NOW.replace(tzinfo=None)}, {"end": NOW + timedelta(days=8)},
                                     {"step_hours": 0}, {"source": "mix&password=x"}, {"latitude": float("nan")}])
def test_bounded_validated_query(changes):
    with pytest.raises(ValueError):
        query(**changes)
