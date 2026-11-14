"""Earthdata adapters: NASADEM_HGT v001 and the explicit SRTMGL1 v003 alternate."""

from analogforge.adapters.earthdata.adapter import (
    NASADEM_ADAPTER_ID,
    SRTMGL1_ADAPTER_ID,
    asset_path,
    decode,
    default_policy,
    discover,
    fetch,
)
from analogforge.adapters.earthdata.nasadem import NasademParams, mosaic

__all__ = [
    "NASADEM_ADAPTER_ID",
    "SRTMGL1_ADAPTER_ID",
    "NasademParams",
    "asset_path",
    "decode",
    "default_policy",
    "discover",
    "fetch",
    "mosaic",
]
