"""Hashing helpers that complement :mod:`analogforge.ports.hashing` (the only canonical-JSON implementation).

Nothing here reimplements RFC 8785; these helpers hash *arrays* and bundle the parameter-hash recipe of
architecture 35 so every module computes ``parameters_sha256`` the same way.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from analogforge.ports.hashing import bytes_sha256, canonical_sha256


def array_sha256(array: NDArray[Any]) -> str:
    """SHA-256 of dtype, shape and little-endian C-contiguous bytes (stable across platforms)."""
    contiguous = np.ascontiguousarray(array)
    if contiguous.dtype.byteorder == ">":
        contiguous = contiguous.astype(contiguous.dtype.newbyteorder("<"))
    digest = hashlib.sha256()
    digest.update(f"{contiguous.dtype.str}|{contiguous.shape}|".encode())
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def parameters_sha256(
    *,
    operation: str,
    algorithm_id: str,
    algorithm_version: str,
    parameters: Mapping[str, Any],
    input_hashes: Sequence[str],
    seed: int,
    algorithm_config_sha256: str,
) -> str:
    """``canonical_sha256({operation, algorithm_id, algorithm_version, parameters, input hashes, seed, config})``."""
    return canonical_sha256(
        {
            "operation": operation,
            "algorithm_id": algorithm_id,
            "algorithm_version": algorithm_version,
            "parameters": dict(parameters),
            "input_hashes": sorted(input_hashes),
            "seed": seed,
            "algorithm_config_sha256": algorithm_config_sha256,
        }
    )


def payload_bytes_sha256(data: bytes) -> str:
    """SHA-256 of raw artifact bytes."""
    return bytes_sha256(data)


__all__ = ["array_sha256", "parameters_sha256", "payload_bytes_sha256"]
