"""EMIT L2B MIN adapter: discovery, NetCDF decode with masks and valid-retrieval statistics."""

from analogforge.adapters.emit.adapter import EMIT_ADAPTER_ID, asset_path, decode, default_policy, discover, fetch
from analogforge.adapters.emit.decode import (
    INVALID_ID,
    EmitDecodeParams,
    RetrievalInBox,
    class_area_fractions,
    retrieval_in_bbox,
)

__all__ = [
    "EMIT_ADAPTER_ID",
    "INVALID_ID",
    "EmitDecodeParams",
    "RetrievalInBox",
    "asset_path",
    "class_area_fractions",
    "decode",
    "default_policy",
    "discover",
    "fetch",
    "retrieval_in_bbox",
]
