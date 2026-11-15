"""Meteomatics point time series with bounded requests and explicit evidence limits.

Sources: https://www.meteomatics.com/en/api/response/json/ and
https://www.meteomatics.com/en/api/response/reserved-values/ .
Credentials stay in HTTP Basic authentication. Provider ``user`` and error bodies
are never copied into results. This module does not read environment variables.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

BASE_URL = "https://api.meteomatics.com"
PARAMETERS = {
    "t_2m:C": ("air_temperature_2m", "C"),
    "wind_speed_10m:ms": ("wind_speed_10m", "m/s"),
    "precip_1h:mm": ("precipitation_previous_1h", "mm"),
    "relative_humidity_2m:p": ("relative_humidity_2m", "%"),
}
RESERVED = frozenset({-999.0, -888.0, -777.0, -666.0})
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
LIMITATIONS = (
    "Earth point weather context for the requested UTC sample window; not a climate normal or site-wide survey.",
    "Two-metre air temperature is not planetary surface brightness temperature or ground temperature.",
    "Provider data may be spatially/temporally interpolated; actual grid support and resolved model are unknown.",
    "Sampled values do not establish continuous conditions between requested times.",
    "Weather context does not qualify a terrain requirement or establish cross-planet environmental equivalence.",
)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Weather timestamps must include a timezone")
    return value.astimezone(UTC)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def _date(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing weather timestamp")
    return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


@dataclass(frozen=True)
class WeatherQuery:
    body: str
    latitude: float
    longitude: float
    start: datetime
    end: datetime
    step_hours: int = 1
    parameters: tuple[str, ...] = ("t_2m:C", "wind_speed_10m:ms", "precip_1h:mm")
    source: str = "mix"

    def __post_init__(self) -> None:
        if self.body not in {"EARTH", "MARS", "MOON"}:
            raise ValueError("Unknown weather body")
        if not math.isfinite(self.latitude) or not -90 <= self.latitude <= 90:
            raise ValueError("Invalid latitude")
        if not math.isfinite(self.longitude) or not -180 <= self.longitude <= 180:
            raise ValueError("Invalid longitude; normalize explicitly to -180..180")
        start, end = utc(self.start), utc(self.end)
        if start.microsecond or end.microsecond:
            raise ValueError("Use whole-second weather timestamps")
        if type(self.step_hours) is not int or not 1 <= self.step_hours <= 24:
            raise ValueError("Weather step must be 1..24 hours")
        seconds = (end - start).total_seconds()
        if not 0 <= seconds <= 7 * 86400 or seconds % (self.step_hours * 3600):
            raise ValueError("Weather window must be step-aligned and at most seven days")
        if not self.parameters or len(set(self.parameters)) != len(self.parameters):
            raise ValueError("Choose distinct weather parameters")
        if any(p not in PARAMETERS for p in self.parameters):
            raise ValueError("Unsupported weather parameter")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.source):
            raise ValueError("Invalid weather source")

    def expected_dates(self) -> tuple[str, ...]:
        count = int((utc(self.end) - utc(self.start)).total_seconds() / (3600 * self.step_hours)) + 1
        return tuple(iso(utc(self.start) + timedelta(hours=i * self.step_hours)) for i in range(count))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "start": iso(self.start), "end": iso(self.end), "parameters": list(self.parameters)}

    def url(self) -> str:
        window = iso(self.start)
        if self.start != self.end:
            window += f"--{iso(self.end)}:PT{self.step_hours}H"
        return f"{BASE_URL}/{window}/{','.join(self.parameters)}/{self.latitude:.8f},{self.longitude:.8f}/json"


@dataclass(frozen=True)
class WeatherContext:
    status: str
    reason_code: str
    query: WeatherQuery
    fetched_at: str
    mode: str
    samples: tuple[dict[str, Any], ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    coverage_fraction: float = 0.0
    limitations: tuple[str, ...] = LIMITATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "reason_code": self.reason_code,
            "body": self.query.body, "query": self.query.to_dict(), "mode": self.mode,
            "fetched_at": self.fetched_at, "samples": list(self.samples),
            "provenance": self.provenance, "coverage_fraction": self.coverage_fraction,
            "limitations": list(self.limitations), "scope": "earth_operating_weather_context",
            "qualification_supported": False,
        }

    def artifact_bytes(self) -> bytes:
        """Persistable normalized evidence: no provider account or authentication fields."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _unknown(query: WeatherQuery, reason: str, mode: str, fetched: datetime) -> WeatherContext:
    return WeatherContext("UNKNOWN", reason, query, iso(fetched), mode)


def parse_weather_response(
    query: WeatherQuery, raw: bytes, *, fetched_at: datetime, mode: str = "live",
) -> WeatherContext:
    """Validate a single requested location/series without inventing absent samples.

    Replay callers must supply previously stored bytes explicitly. They never
    fall back to live acquisition. A response hash covers the exact input bytes;
    only the normalized, account-free artifact is suitable for UI delivery.
    """
    if mode not in {"live", "replay"}:
        return _unknown(query, "MODE_UNSUPPORTED", mode, fetched_at)
    if query.body != "EARTH":
        return _unknown(query, "EARTH_PROVIDER_BODY_MISMATCH", mode, fetched_at)
    if len(raw) > MAX_RESPONSE_BYTES:
        return _unknown(query, "RESOURCE_LIMIT", mode, fetched_at)
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("status") != "OK":
            raise ValueError("Provider status is not OK")
        generated = iso(_date(payload.get("dateGenerated")))
        entries = payload["data"]
        if not isinstance(entries, list) or len(entries) > len(query.parameters):
            raise ValueError("Unexpected parameter entries")
        expected = set(query.expected_dates())
        samples: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        seen_parameters: set[str] = set()
        for series in entries:
            parameter = series["parameter"]
            if parameter not in query.parameters or parameter in seen_parameters:
                raise ValueError("Unexpected or duplicate parameter")
            seen_parameters.add(parameter)
            coordinates = series["coordinates"]
            if not isinstance(coordinates, list) or len(coordinates) != 1:
                raise ValueError("Unexpected coordinates")
            point = coordinates[0]
            latitude, longitude = float(point["lat"]), float(point["lon"])
            if (not math.isfinite(latitude) or not math.isfinite(longitude)
                    or abs(latitude - query.latitude) > 1e-6 or abs(longitude - query.longitude) > 1e-6):
                raise ValueError("Coordinate mismatch")
            dates = point["dates"]
            if not isinstance(dates, list) or len(dates) > len(expected):
                raise ValueError("Unexpected dates")
            for item in dates:
                date = iso(_date(item["date"]))
                key = parameter, date
                if date not in expected or key in seen:
                    raise ValueError("Unexpected or duplicate timestamp")
                seen.add(key)
                raw_value = item.get("value")
                value = (float(raw_value)
                         if isinstance(raw_value, int | float) and not isinstance(raw_value, bool) else None)
                if value is not None and (not math.isfinite(value) or value in RESERVED):
                    value = None
                # Nonnegative speed/precipitation and physical temperature/humidity.
                if value is not None and (
                    (parameter in {"wind_speed_10m:ms", "precip_1h:mm"} and value < 0)
                    or (parameter == "t_2m:C" and value <= -273.15)
                    or (parameter == "relative_humidity_2m:p" and not 0 <= value <= 100)
                ):
                    value = None
                quantity, unit = PARAMETERS[parameter]
                samples.append({"parameter": parameter, "quantity": quantity, "unit": unit,
                                "valid_at": date, "value": value,
                                "reason_code": "VALUE_AVAILABLE" if value is not None else "PROVIDER_VALUE_MISSING"})
    except (ValueError, KeyError, TypeError, OverflowError):
        return _unknown(query, "SOURCE_CONTENT_INVALID", mode, fetched_at)
    denominator = len(query.expected_dates()) * len(query.parameters)
    valid_count = sum(s["value"] is not None for s in samples)
    coverage = valid_count / denominator
    status = "AVAILABLE" if valid_count == denominator else "LIMITED" if valid_count else "UNKNOWN"
    provenance = {
        "provider": "Meteomatics", "source_url": query.url(), "requested_source": query.source,
        "resolved_model": None, "spatial_support_m": None, "date_generated": generated,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_bytes": len(raw), "expected_sample_count": denominator, "valid_sample_count": valid_count,
        "documentation_url": "https://www.meteomatics.com/en/api/response/json/",
        "license_note": "Use subject to the connected Meteomatics account's data license.",
    }
    ordered = tuple(sorted(samples, key=lambda s: (s["valid_at"], s["parameter"])))
    return WeatherContext(status, "COMPLETE_SAMPLE_WINDOW" if status == "AVAILABLE" else "INCOMPLETE_SAMPLE_WINDOW",
                          query, iso(fetched_at), mode, ordered, provenance, coverage)


def fetch_earth_weather(
    query: WeatherQuery, *, client: httpx.Client | None, username: str | None = None,
    password: str | None = None, mode: str = "live", fetched_at: datetime | None = None,
    timeout_seconds: float = 20, check_cancelled: Callable[[], None] | None = None,
) -> WeatherContext:
    """One bounded HTTPS request. Non-live modes and non-Earth bodies never use HTTP."""
    fetched = utc(fetched_at or datetime.now(UTC))
    if query.body != "EARTH":
        return _unknown(query, "EARTH_PROVIDER_BODY_MISMATCH", mode, fetched)
    if mode != "live":
        return _unknown(query, "NETWORK_DISABLED_FOR_MODE", mode, fetched)
    if client is None or not username or not password:
        return _unknown(query, "WEATHER_NOT_CONFIGURED", mode, fetched)
    if check_cancelled is not None:
        check_cancelled()
    try:
        # Do not follow redirects carrying Basic authentication to another origin.
        with client.stream("GET", query.url(), params={"source": query.source},
                           auth=httpx.BasicAuth(username, password), timeout=timeout_seconds,
                           follow_redirects=False) as response:
            if response.status_code != 200:
                reason = "WEATHER_AUTH_FAILED" if response.status_code in {401, 403} else "SOURCE_UNAVAILABLE"
                return _unknown(query, reason, mode, fetched)
            data = bytearray()
            for block in response.iter_bytes(chunk_size=32768):
                if check_cancelled is not None:
                    check_cancelled()
                data.extend(block)
                if len(data) > MAX_RESPONSE_BYTES:
                    return _unknown(query, "RESOURCE_LIMIT", mode, fetched)
    except httpx.HTTPError:
        return _unknown(query, "SOURCE_UNAVAILABLE", mode, fetched)
    result = parse_weather_response(query, bytes(data), fetched_at=fetched, mode=mode)
    if check_cancelled is not None:
        check_cancelled()
    return result
