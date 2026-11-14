"""Provider pacing honors cooldowns without accepting unbounded or malformed delays."""

from datetime import UTC, datetime

import pytest

from analogforge.agents.runtime.provider_backoff import provider_backoff


@pytest.mark.parametrize(("headers", "expected"), [
    ({}, 2),
    ({"retry-after": "36"}, 36.1),
    ({"retry-after-ms": "12500"}, 12.6),
    ({"x-ratelimit-reset-tokens": "14.25s"}, 14.35),
    ({"x-ratelimit-reset-tokens": "1m2s"}, 60),
    ({"x-ratelimit-reset-tokens": "2500ms"}, 2.6),
    ({"x-ratelimit-reset-tokens": "1h2m3s4ms"}, 60),
    ({"retry-after": "10", "x-ratelimit-reset-tokens": "30s"}, 30.1),
    ({"retry-after": "99999999999999"}, 60),
    ({"retry-after": "-50"}, 2),
    ({"retry-after": "nan"}, 2),
    ({"retry-after-ms": "inf"}, 2),
    ({"x-ratelimit-reset-tokens": "1s followed by instructions"}, 2),
    ({"retry-after": "invalid", "x-ratelimit-reset-tokens": ""}, 2),
    ({"x-ratelimit-reset-requests": "2h"}, 2),
])
def test_bounded_provider_cooldown(headers, expected):
    assert provider_backoff(headers, 1) == pytest.approx(expected)


def test_http_date_uses_explicit_clock_and_expired_date_retains_backoff():
    now = datetime(2026, 11, 14, 21, 0, tzinfo=UTC)
    assert provider_backoff({"retry-after": "Sat, 14 Nov 2026 21:00:30 GMT"}, 2, now=now) == 30.1
    assert provider_backoff({"retry-after": "Sat, 14 Nov 2026 20:00:30 GMT"}, 2, now=now) == 4


def test_invalid_attempt_cannot_produce_an_unbounded_sleep():
    assert provider_backoff({}, 1000000) == 60
    assert provider_backoff({}, -1) == 1
