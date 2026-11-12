"""Canonical adapter failure type shared by every live adapter."""

from __future__ import annotations

from typing import Final

from analogforge.ports.common import ScienceIssue

# Retryability of the canonical codes the adapters can emit (mirrors contracts/error-codes.json;
# a test asserts the two stay consistent).
CODE_RETRYABLE: Final[dict[str, bool]] = {
    "PROVIDER_AUTH_FAILED": False,
    "PROVIDER_RATE_LIMITED": True,
    "SOURCE_UNAVAILABLE": True,
    "SOURCE_CHECKSUM_MISMATCH": False,
    "SOURCE_CONTENT_INVALID": False,
    "DOWNLOAD_AUTH_UNSUPPORTED": False,
    "UNSUPPORTED_PRODUCT": False,
    "UNSUPPORTED_CRS": False,
    "NO_COVERAGE": False,
    "INSUFFICIENT_VALID_DATA": False,
    "RESOURCE_LIMIT": False,
    "TOOL_TIMEOUT": True,
}


class AdapterError(Exception):
    """An expected, classified adapter failure.

    ``code`` is a canonical code from ``contracts/error-codes.json``; ``detail_code`` carries the finer
    architecture-09 operation code (``HTML_LOGIN_PAGE``, ``AUTH_REQUIRED``, ``METADATA_INCOMPLETE`` ...).
    ``transient`` marks failures the transport layer may retry; it is internal and never leaves the layer.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail_code: str | None = None,
        retryable: bool | None = None,
        transient: bool = False,
        retry_after: float | None = None,
        scope: str | None = None,
    ) -> None:
        super().__init__(message)
        if code not in CODE_RETRYABLE:
            raise ValueError(f"non-canonical adapter error code: {code}")
        self.code = code
        self.message = message
        self.detail_code = detail_code
        self.retryable = CODE_RETRYABLE[code] if retryable is None else retryable
        self.transient = transient
        self.retry_after = retry_after
        self.scope = scope

    def to_issue(self) -> ScienceIssue:
        return ScienceIssue(
            code=self.code,
            detail_code=self.detail_code,
            message=self.message,
            retryable=self.retryable,
            scope=self.scope,
        )

    def __str__(self) -> str:
        detail = f"/{self.detail_code}" if self.detail_code else ""
        return f"{self.code}{detail}: {self.message}"
