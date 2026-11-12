"""Shared HTTP origin policy and non-secret response hardening."""

from collections.abc import Collection

from fastapi import Request

from analogforge.api.errors import ApiError


def origin_allowed(origin: str | None, allowed_origins: Collection[str]) -> bool:
    """Native clients may omit Origin; browsers must match an exact configured origin."""
    return origin is None or origin in allowed_origins


def response_headers(request_id: str) -> dict[str, str]:
    return {
        "X-Request-ID": request_id,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }


async def read_bounded_json_body(request: Request, limit: int = 262144) -> bytes:
    """Bound the buffer even when a client omits or lies about Content-Length."""
    parts = bytearray()
    async for chunk in request.stream():
        if len(parts) + len(chunk) > limit:
            raise ApiError("INPUT_TOO_LARGE", "The request exceeds the supported input size.", 413)
        parts.extend(chunk)
    return bytes(parts)
