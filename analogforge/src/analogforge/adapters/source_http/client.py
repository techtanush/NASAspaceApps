"""Safe HTTP access over an injected ``httpx.Client``.

The client (and any credential it carries) is supplied by the caller; this module never reads the
environment and never creates a client of its own. Redirects are followed manually so every hop is
validated against the allow-list and credentials are removed from any hop that is not an approved
credential host.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.policy import HttpPolicy

T = TypeVar("T")

_REDIRECTS = {301, 302, 303, 307, 308}
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
_BINARY_FALLBACK_TYPES = ("application/octet-stream", "binary/octet-stream")
_HTML_SNIFF = re.compile(rb"^\s*(<!doctype\s+html|<html|<head|<body)", re.IGNORECASE)
_CHUNK = 1 << 16


def redact_url(url: str) -> str:
    """Stable identity for a URL: scheme+host+path only (no userinfo, query or fragment)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def has_credentials(client: httpx.Client | None) -> bool:
    """True when the injected client carries an Authorization header or an auth handler."""
    if client is None:
        return False
    return "authorization" in client.headers or client.auth is not None


def looks_like_html(head: bytes) -> bool:
    return bool(_HTML_SNIFF.match(head))


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


@dataclass(frozen=True)
class ExpectedChecksum:
    algorithm: str  # "sha256" | "md5"
    value: str

    def __post_init__(self) -> None:
        if self.algorithm not in {"sha256", "md5"}:
            raise ValueError(f"unsupported checksum algorithm: {self.algorithm}")


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    sha256: str
    size_bytes: int
    content_type: str | None
    source_uri: str  # redacted, stable
    final_uri: str  # redacted, after redirects
    redirect_hosts: tuple[str, ...]
    provider_checksum_verified: bool


@dataclass(frozen=True)
class FetchedBytes:
    content: bytes
    headers: Mapping[str, str]
    final_uri: str


class SafeHttp:
    """GET-only, allow-listed, bounded, retrying HTTP access."""

    def __init__(self, client: httpx.Client, policy: HttpPolicy) -> None:
        self._client = client
        self._policy = policy

    @property
    def policy(self) -> HttpPolicy:
        return self._policy

    @property
    def has_credentials(self) -> bool:
        return has_credentials(self._client)

    # ------------------------------------------------------------------ retry core
    def _with_retries(self, action: Callable[[], T]) -> T:
        policy = self._policy
        for attempt in range(1, policy.max_attempts + 1):
            try:
                return action()
            except AdapterError as err:
                if not err.transient or attempt == policy.max_attempts:
                    raise
                if err.retry_after is not None:
                    if err.retry_after > policy.max_retry_after_s:
                        raise
                    delay = err.retry_after
                else:
                    delay = policy.backoff_s[min(attempt - 1, len(policy.backoff_s) - 1)]
                policy.sleep(delay)
        raise AssertionError("unreachable: max_attempts >= 1")  # pragma: no cover

    # ------------------------------------------------------------------ one attempt
    def _check_host(self, url: str) -> str:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" and not (self._policy.allow_insecure and parts.scheme == "http"):
            raise AdapterError(
                "SOURCE_CONTENT_INVALID",
                f"refusing non-https URL scheme for {redact_url(url)}",
                detail_code="INSECURE_SCHEME",
            )
        if parts.username or parts.password:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID", "URLs with embedded credentials are refused", detail_code="URL_CREDENTIALS"
            )
        if host not in self._policy.allowed_hosts:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID",
                f"host {host!r} is not on the adapter allow-list",
                detail_code="HOST_NOT_ALLOWED",
            )
        return host

    def _open(
        self, url: str, params: Mapping[str, Any] | None, headers: Mapping[str, str] | None
    ) -> tuple[httpx.Response, tuple[str, ...]]:
        """Send one GET following redirects manually; returns an open streamed response."""
        policy = self._policy
        initial_host = self._check_host(url)
        credential_hosts = policy.auth_hosts | {initial_host}
        current = url
        hosts: list[str] = [initial_host]
        for hop in range(policy.max_redirects + 1):
            host = self._check_host(current)
            request = self._client.build_request(
                "GET", current, params=params if hop == 0 else None, headers=dict(headers) if headers else None
            )
            send_auth: Any = httpx.USE_CLIENT_DEFAULT
            if host not in credential_hosts:
                for name in ("authorization", "cookie", "proxy-authorization"):
                    if name in request.headers:
                        del request.headers[name]
                send_auth = None
            try:
                response = self._client.send(request, stream=True, follow_redirects=False, auth=send_auth)
            except httpx.TimeoutException as exc:
                raise AdapterError("TOOL_TIMEOUT", f"timeout contacting {host}", transient=True) from exc
            except httpx.RequestError as exc:
                raise AdapterError(
                    "SOURCE_UNAVAILABLE", f"transport error contacting {host}: {type(exc).__name__}", transient=True
                ) from exc
            if response.status_code in _REDIRECTS:
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID", "redirect without Location header", detail_code="BAD_REDIRECT"
                    )
                current = urljoin(str(request.url), location)
                hosts.append((urlsplit(current).hostname or "").lower())
                continue
            return response, tuple(hosts)
        raise AdapterError("SOURCE_UNAVAILABLE", "too many redirects", detail_code="TOO_MANY_REDIRECTS")

    def _classify_status(self, response: httpx.Response, url: str) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        response.close()
        where = redact_url(url)
        if status in (401, 403):
            raise AdapterError(
                "PROVIDER_AUTH_FAILED", f"authentication required or rejected by {where}", detail_code="AUTH_REQUIRED"
            )
        if status == 429:
            raise AdapterError(
                "PROVIDER_RATE_LIMITED", f"rate limited by {where}", transient=True, retry_after=retry_after
            )
        if status in _TRANSIENT_STATUS:
            raise AdapterError(
                "SOURCE_UNAVAILABLE",
                f"HTTP {status} from {where}",
                detail_code=f"HTTP_{status}",
                transient=True,
                retry_after=retry_after,
            )
        if status in (404, 410):
            raise AdapterError("SOURCE_UNAVAILABLE", f"{where} not found", detail_code="NOT_FOUND", retryable=False)
        raise AdapterError(
            "SOURCE_UNAVAILABLE", f"HTTP {status} from {where}", detail_code=f"HTTP_{status}", retryable=False
        )

    # ------------------------------------------------------------------ small bodies
    def get_bytes(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
        allow_html: bool = False,
    ) -> FetchedBytes:
        limit = max_bytes if max_bytes is not None else self._policy.max_metadata_bytes

        def attempt() -> FetchedBytes:
            response, _ = self._open(url, params, headers)
            try:
                self._classify_status(response, url)
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > limit:
                    raise AdapterError("RESOURCE_LIMIT", f"{redact_url(url)} exceeds {limit} byte metadata limit")
                chunks: list[bytes] = []
                total = 0
                try:
                    for chunk in response.iter_bytes(_CHUNK):
                        total += len(chunk)
                        if total > limit:
                            raise AdapterError(
                                "RESOURCE_LIMIT", f"{redact_url(url)} exceeds {limit} byte metadata limit"
                            )
                        chunks.append(chunk)
                except httpx.RequestError as exc:
                    raise AdapterError("SOURCE_UNAVAILABLE", "connection dropped mid-body", transient=True) from exc
                body = b"".join(chunks)
                if not allow_html and (
                    looks_like_html(body[:512])
                    or response.headers.get("content-type", "").lower().startswith("text/html")
                ):
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID",
                        f"{redact_url(url)} returned an HTML page",
                        detail_code="HTML_LOGIN_PAGE",
                    )
                return FetchedBytes(
                    body, {k.lower(): v for k, v in response.headers.items()}, redact_url(str(response.url))
                )
            finally:
                response.close()

        return self._with_retries(attempt)

    def get_json(
        self, url: str, *, params: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None
    ) -> tuple[Any, Mapping[str, str]]:
        fetched = self.get_bytes(url, params=params, headers=headers)
        try:
            return json.loads(fetched.content), fetched.headers
        except (ValueError, UnicodeDecodeError) as exc:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID", f"{redact_url(url)} did not return JSON", detail_code="NOT_JSON"
            ) from exc

    # ------------------------------------------------------------------ large bodies
    def download(
        self,
        url: str,
        dest: Path,
        *,
        expected: ExpectedChecksum | None = None,
        max_bytes: int | None = None,
        accept_content_types: tuple[str, ...] | None = None,
        expected_magic: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> DownloadResult:
        """Stream ``url`` to ``dest`` atomically with every safety check; a partial file never survives."""
        limit = max_bytes if max_bytes is not None else self._policy.max_download_bytes
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")

        def attempt() -> DownloadResult:
            response, hosts = self._open(url, None, headers)
            try:
                self._classify_status(response, url)
                ctype = response.headers.get("content-type")
                base_type = (ctype or "").split(";")[0].strip().lower()
                if base_type == "text/html" and not (accept_content_types and "text/html" in accept_content_types):
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID",
                        f"{redact_url(url)} returned an HTML page",
                        detail_code="HTML_LOGIN_PAGE",
                    )
                if (
                    accept_content_types
                    and base_type
                    and base_type not in accept_content_types
                    and base_type not in _BINARY_FALLBACK_TYPES
                ):
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID",
                        f"unexpected content type {base_type!r}",
                        detail_code="CONTENT_TYPE_UNEXPECTED",
                    )
                declared = response.headers.get("content-length")
                declared_len = int(declared) if declared and declared.isdigit() else None
                if declared_len is not None and declared_len > limit:
                    raise AdapterError("RESOURCE_LIMIT", f"declared size {declared_len} exceeds limit {limit}")
                sha = hashlib.sha256()
                md5 = hashlib.md5(usedforsecurity=False)
                total = 0
                head = b""
                try:
                    with part.open("wb") as handle:
                        for chunk in response.iter_bytes(_CHUNK):
                            if not head:
                                head = chunk[:512]
                                if looks_like_html(head) and not (
                                    accept_content_types and "text/html" in accept_content_types
                                ):
                                    raise AdapterError(
                                        "SOURCE_CONTENT_INVALID",
                                        f"{redact_url(url)} returned an HTML page",
                                        detail_code="HTML_LOGIN_PAGE",
                                    )
                            total += len(chunk)
                            if total > limit:
                                raise AdapterError("RESOURCE_LIMIT", f"download exceeds {limit} byte limit")
                            sha.update(chunk)
                            md5.update(chunk)
                            handle.write(chunk)
                except httpx.RequestError as exc:
                    raise AdapterError("SOURCE_UNAVAILABLE", "connection dropped mid-body", transient=True) from exc
                encoded = response.headers.get("content-encoding", "identity").lower() != "identity"
                if declared_len is not None and not encoded and declared_len != total:
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID",
                        f"truncated transfer: declared {declared_len} bytes, received {total}",
                        detail_code="TRUNCATED_TRANSFER",
                        transient=True,
                    )
                if total == 0:
                    raise AdapterError("SOURCE_CONTENT_INVALID", "empty response body", detail_code="EMPTY_BODY")
                if expected_magic is not None and not head.startswith(expected_magic):
                    raise AdapterError(
                        "SOURCE_CONTENT_INVALID",
                        "content does not start with the expected signature",
                        detail_code="MAGIC_MISMATCH",
                    )
                digest = sha.hexdigest()
                verified = False
                if expected is not None:
                    actual = digest if expected.algorithm == "sha256" else md5.hexdigest()
                    if actual != expected.value.strip().lower():
                        raise AdapterError(
                            "SOURCE_CHECKSUM_MISMATCH",
                            f"{expected.algorithm} mismatch for {redact_url(url)}; bytes quarantined",
                            detail_code="CHECKSUM_MISMATCH",
                        )
                    verified = True
                part.replace(dest)
                return DownloadResult(
                    dest, digest, total, ctype, redact_url(url), redact_url(str(response.url)), hosts, verified
                )
            finally:
                response.close()
                part.unlink(missing_ok=True)

        return self._with_retries(attempt)
