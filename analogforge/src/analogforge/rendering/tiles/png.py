"""Deterministic PNG encoding/decoding for RGBA display images (Pillow).

Determinism: fixed compression level, no ``optimize`` pass, no ancillary chunks (no timestamp, no software tag), so
equal pixels always produce identical bytes on one Pillow/zlib build.
"""

from __future__ import annotations

import io

import numpy as np
from numpy.typing import NDArray
from PIL import Image

UInt8Array = NDArray[np.uint8]
PNG_MEDIA_TYPE = "image/png"
_COMPRESS_LEVEL = 6


def encode_png_rgba(rgba: UInt8Array) -> bytes:
    """Encode an ``(H, W, 4)`` uint8 array as an RGBA PNG."""
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("encode_png_rgba needs a uint8 array of shape (H, W, 4)")
    if rgba.shape[0] < 1 or rgba.shape[1] < 1:
        raise ValueError("image needs at least one pixel")
    image = Image.fromarray(np.ascontiguousarray(rgba), mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=_COMPRESS_LEVEL)
    return buffer.getvalue()


def decode_png_rgba(data: bytes) -> UInt8Array:
    """Decode PNG bytes to an ``(H, W, 4)`` uint8 array (used by tests and the facade's self-checks)."""
    with Image.open(io.BytesIO(data)) as image:
        converted = image.convert("RGBA")
        return np.asarray(converted, dtype=np.uint8).copy()


__all__ = ["PNG_MEDIA_TYPE", "decode_png_rgba", "encode_png_rgba"]
