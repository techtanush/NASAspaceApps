"""Honor short provider cooldowns without increasing the fixed transport retry budget."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

_RESET = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?")


def provider_backoff(headers: Mapping[str, str], attempt: int, *, now: datetime | None = None) -> float:
    """Return a finite delay of at most 60s; malformed headers retain exponential backoff."""
    delays = [min(60.0, float(2 ** min(max(attempt, 0), 6)))]
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            delay = float(value) * scale
        except ValueError:
            if name != "retry-after":
                continue
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                delay = (date - (now or datetime.now(UTC))).total_seconds()
            except (TypeError, ValueError, OverflowError):
                continue
        if math.isfinite(delay) and delay >= 0:
            delays.append(min(60.0, delay + 0.1))
    reset = headers.get("x-ratelimit-reset-tokens", "")
    match = _RESET.fullmatch(reset)
    if match and any(match.groups()):
        delay = sum(float(value or 0) * scale
                    for value, scale in zip(match.groups(), (3600, 60, 1, 0.001), strict=True))
        if math.isfinite(delay):
            delays.append(min(60.0, delay + 0.1))
    return max(delays)
