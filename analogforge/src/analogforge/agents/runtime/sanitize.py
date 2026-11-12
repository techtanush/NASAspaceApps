"""Secrets and provider hidden reasoning never enter public diagnostics."""

import re
from typing import Any

SECRET_KEYS = frozenset(
    {
        "api_key",
        "openai_api_key",
        "earthdata_token",
        "authorization",
        "database_url",
        "lease_token",
        "reasoning",
        "chain_of_thought",
    }
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k.lower() not in SECRET_KEYS}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        value = re.sub(r"postgres(?:ql)?(?:\+psycopg)?://[^\s]+", "[REDACTED]", value)
        value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._-]+", "[REDACTED]", value)
    return value
