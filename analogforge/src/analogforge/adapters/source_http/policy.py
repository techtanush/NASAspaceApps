"""Transport policy for the shared safe-HTTP layer."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

DEFAULT_BACKOFF_S: tuple[float, ...] = (2.0, 4.0)
# Headers that carry a credential: stripped on every hop to a host that is not an approved credential host.
DEFAULT_SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "x-api-key",
        "api-key",
        "x-auth-token",
        "x-access-token",
        "x-amz-security-token",
        "x-csrf-token",
    }
)
_SENSITIVE_MARKERS: tuple[str, ...] = (
    "auth",
    "token",
    "secret",
    "key",
    "cookie",
    "credential",
    "password",
    "signature",
)


@dataclass(frozen=True)
class HttpPolicy:
    """Everything the safe-HTTP layer needs to decide what is permitted.

    * ``allowed_hosts`` - exact host names a request or redirect hop may target (https only unless
      ``allow_insecure``; the latter exists for tests that must not use TLS names).
    * ``auth_hosts`` - extra hosts (beyond the host of the initial URL) that may receive credentials.
      Any other hop has every credential-like header stripped before it is sent: the names in
      ``sensitive_headers`` plus any header whose name contains ``auth``, ``token``, ``secret``, ``key``,
      ``cookie``, ``credential``, ``password`` or ``signature``.
    * ``allowed_ports`` - ports a request or redirect hop may target (default 443 only; port 80 is added when
      ``allow_insecure``).  A hop to an allow-listed host on any other port is refused.
    * ``max_attempts`` transport attempts (never more than 3) with ``backoff_s`` sleeps between them;
      a ``Retry-After`` header replaces the back-off value when present and is refused above
      ``max_retry_after_s``.
    * ``sleep`` is injectable so tests never wait.
    """

    allowed_hosts: frozenset[str]
    auth_hosts: frozenset[str] = frozenset()
    max_attempts: int = 3
    backoff_s: tuple[float, ...] = DEFAULT_BACKOFF_S
    max_retry_after_s: float = 60.0
    max_redirects: int = 5
    max_download_bytes: int = 512 * 1024 * 1024
    max_metadata_bytes: int = 16 * 1024 * 1024
    allow_insecure: bool = False
    allowed_ports: frozenset[int] = frozenset({443})
    sensitive_headers: frozenset[str] = DEFAULT_SENSITIVE_HEADERS
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False)

    @property
    def permitted_ports(self) -> frozenset[int]:
        return self.allowed_ports | ({80} if self.allow_insecure else frozenset())

    def is_sensitive_header(self, name: str) -> bool:
        lowered = name.lower()
        return lowered in self.sensitive_headers or any(marker in lowered for marker in _SENSITIVE_MARKERS)

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if not self.backoff_s:
            raise ValueError("backoff_s must not be empty")
        if self.max_download_bytes <= 0 or self.max_metadata_bytes <= 0:
            raise ValueError("byte limits must be positive")
