"""Explicit fallback capabilities; credentials never participate in diagnostics."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import SecretStr

FallbackProvider = Literal["groq", "openrouter", "anthropic", "sambanova", "nvidia", "gemini"]

SUPPORTED_PROVIDERS = {"groq", "openrouter", "anthropic", "sambanova", "nvidia", "gemini"}


@dataclass(frozen=True)
class FallbackConfig:
    provider: FallbackProvider
    model: str
    api_key: SecretStr = field(repr=False)
    upstream: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("Unsupported strict-tool fallback provider")
        if not self.model.strip() or not self.api_key.get_secret_value():
            raise ValueError("Fallback requires an explicit model and credential")
        if self.provider == "openrouter" and not self.upstream:
            raise ValueError("OpenRouter requires one explicitly pinned upstream")
