"""Transport policy for the shared safe-HTTP layer."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

DEFAULT_BACKOFF_S: tuple[float, ...] = (2.0, 4.0)


@dataclass(frozen=True)
class HttpPolicy:
    """Everything the safe-HTTP layer needs to decide what is permitted.

    * ``allowed_hosts`` - exact host names a request or redirect hop may target (https only unless
      ``allow_insecure``; the latter exists for tests that must not use TLS names).
    * ``auth_hosts`` - extra hosts (beyond the host of the initial URL) that may receive credentials.
      Any other hop has ``Authorization``/``Cookie`` stripped before it is sent.
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
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False)

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if not self.backoff_s:
            raise ValueError("backoff_s must not be empty")
        if self.max_download_bytes <= 0 or self.max_metadata_bytes <= 0:
            raise ValueError("byte limits must be positive")
