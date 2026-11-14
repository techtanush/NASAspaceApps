"""Shared safe-HTTP layer for the live source adapters (validated only against mocked transports)."""

from analogforge.adapters.source_http.archive import ArchiveLimits, safe_extract_zip
from analogforge.adapters.source_http.client import (
    DownloadResult,
    ExpectedChecksum,
    FetchedBytes,
    SafeHttp,
    has_credentials,
    redact_url,
)
from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.policy import HttpPolicy

__all__ = [
    "AdapterError",
    "ArchiveLimits",
    "DecodedRaster",
    "DownloadResult",
    "ExpectedChecksum",
    "FetchedBytes",
    "HttpPolicy",
    "RasterMetadata",
    "SafeHttp",
    "has_credentials",
    "redact_url",
    "safe_extract_zip",
]
