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


#: Contract bodies nest a handful of levels (the deepest kit fixture is far below half of this). The bound stops runaway
#: structures before any recursive parser, hasher or schema validator touches them.
MAX_JSON_DEPTH = 64


def json_nesting_depth(raw: bytes, limit: int | None = None) -> int:
    """Maximum object/array nesting of a JSON document, ignoring brackets inside strings, without recursion.

    Stops counting once ``limit`` is exceeded, so the scan is bounded even for a hostile body.
    """
    depth = deepest = 0
    in_string = escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:  # backslash
                escaped = True
            elif byte == 0x22:  # closing quote
                in_string = False
        elif byte == 0x22:
            in_string = True
        elif byte in (0x5B, 0x7B):  # [ {
            depth += 1
            deepest = max(deepest, depth)
            if limit is not None and deepest > limit:
                return deepest
        elif byte in (0x5D, 0x7D):  # ] }
            depth = max(0, depth - 1)
    return deepest


async def read_bounded_json_body(request: Request, limit: int = 262144) -> bytes:
    """Bound the buffer even when a client omits or lies about Content-Length."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise ApiError("INPUT_TOO_LARGE", "The request exceeds the supported input size.", 413)
    parts = bytearray()
    async for chunk in request.stream():
        if len(parts) + len(chunk) > limit:
            raise ApiError("INPUT_TOO_LARGE", "The request exceeds the supported input size.", 413)
        parts.extend(chunk)
    return bytes(parts)
