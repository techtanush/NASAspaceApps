"""Bounded Responses routing; separate credentials, explicit models, no SDK retries."""

import math
import threading
import time
from collections.abc import Callable
from typing import Any, cast

from openai import APIStatusError, OpenAI
from pydantic import SecretStr

from analogforge.adapters.openai.anthropic import AnthropicMessages
from analogforge.adapters.openai.envelope import JsonToolEnvelope
from analogforge.adapters.openai.fallback import FallbackConfig
from analogforge.agents.runtime.provider import ProviderError


def fallback_options(settings: Any) -> dict[str, Any]:
    key = getattr(settings, "groq_api_key", None)
    options = {
        "groq_api_key": key.get_secret_value() if key is not None else None,
        "groq_model": getattr(settings, "groq_model", None),
        "groq_fallback_enabled": getattr(settings, "groq_fallback_enabled", False),
    }
    order = getattr(settings, "model_fallback_order", None)
    if order is not None:
        options["fallbacks"] = tuple(FallbackConfig(
            provider=provider, model=getattr(settings, provider + "_model"),
            api_key=getattr(settings, provider + "_api_key"),
            upstream=getattr(settings, "openrouter_upstream", None) if provider == "openrouter" else None,
        ) for provider in order)
    return options


class RateLimitCooldown:
    """Share only a deadline across invocations, never prompts or responses."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.until = 0.0
        self.next_request_at = 0.0
        self.lock = threading.Lock()
        self.provider_deadlines: dict[str, float] = {}

    def wait_for_slot(self, interval: float, sleep: Callable[[float], None]) -> None:
        """Reserve a process-shared request slot without retaining conversation data.

        Pacing is optional, local, and separate from provider retry/correction budgets.
        A failed attempt still consumes its reserved slot. No lock is held during sleep.
        """
        if interval == 0:
            return
        with self.lock:
            now = self.clock()
            reserved = max(now, self.next_request_at)
            self.next_request_at = reserved + interval
        delay = max(0.0, reserved - now)
        if delay:
            sleep(delay)

    def active(self, provider: str = "openai") -> bool:
        with self.lock:
            return self.clock() < (self.until if provider == "openai" else self.provider_deadlines.get(provider, 0))

    def limited(self, retry_after: str | None, provider: str = "openai") -> None:
        try:
            seconds = float(retry_after or "60")
        except ValueError:
            seconds = 60.0
        seconds = min(300.0, max(1.0, seconds)) if math.isfinite(seconds) else 60.0
        with self.lock:
            if provider == "openai":
                self.until = max(self.until, self.clock() + seconds)
            else:
                self.provider_deadlines[provider] = max(
                    self.provider_deadlines.get(provider, 0), self.clock() + seconds,
                )


def portable_input(value: Any) -> Any:
    """Replay explicit messages/tool records, excluding vendor reasoning and opaque IDs."""
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ProviderError("MODEL_OUTPUT_INVALID", "Unsupported provider continuation")
    items = []
    for item in value:
        kind = item.get("type", "message")
        if kind == "reasoning":
            continue
        if kind == "function_call":
            items.append({key: item[key] for key in ("type", "name", "call_id", "arguments")})
        elif kind == "function_call_output":
            items.append({key: item[key] for key in ("type", "call_id", "output")})
        elif kind == "message" and item.get("role") in {"user", "assistant", "system", "developer"}:
            content = item["content"]
            if isinstance(content, list):
                if any(part.get("type") not in {"input_text", "output_text"} for part in content):
                    raise ProviderError("MODEL_OUTPUT_INVALID", "Unsupported provider message content")
                content = "\n".join(part["text"] for part in content)
            items.append({"role": item["role"], "content": content})
        else:
            raise ProviderError("MODEL_OUTPUT_INVALID", "Unsupported provider continuation item")
    return items


class ResponsesClient:
    def __init__(
        self, api_key: str | None, model: str | None, *, base_url: str | None = None, timeout: float = 30,
        groq_api_key: str | None = None, groq_model: str | None = None, groq_fallback_enabled: bool = False,
        cooldown: RateLimitCooldown | None = None,
        min_request_interval_seconds: float = 0, sleep: Callable[[float], None] = time.sleep,
        primary_output_token_limit: int = 4096,
        primary_reasoning_effort: str | None = None,
        nvidia_output_token_limit: int = 1024,
        fallbacks: tuple[FallbackConfig, ...] | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_API_KEY is required")
        if not model:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_MODEL is required")
        if not math.isfinite(min_request_interval_seconds) or not 0 <= min_request_interval_seconds <= 60:
            raise ValueError("Provider request pacing must be between 0 and 60 seconds")
        self.min_request_interval_seconds = min_request_interval_seconds
        if (isinstance(primary_output_token_limit, bool) or not isinstance(primary_output_token_limit, int)
                or not 256 <= primary_output_token_limit <= 4096):
            raise ValueError("Primary output token limit must be between 256 and 4096")
        self.primary_output_token_limit = primary_output_token_limit
        if primary_reasoning_effort is not None and primary_reasoning_effort not in {
            "none", "low", "medium", "high", "xhigh"
        }:
            raise ValueError("Invalid primary reasoning effort")
        self.primary_reasoning_effort = primary_reasoning_effort
        if (isinstance(nvidia_output_token_limit, bool) or not isinstance(nvidia_output_token_limit, int)
                or not 256 <= nvidia_output_token_limit <= 4096):
            raise ValueError("NVIDIA output token limit must be between 256 and 4096")
        self.nvidia_output_token_limit = nvidia_output_token_limit
        self.sleep = sleep
        self.model = model
        self.primary_model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
        if fallbacks is None and groq_fallback_enabled and not (groq_api_key and groq_model):
            raise ProviderError("PROVIDER_AUTH_FAILED", "Groq fallback requires GROQ_API_KEY and GROQ_MODEL")
        if fallbacks is None:
            fallbacks = (FallbackConfig("groq", groq_model, SecretStr(groq_api_key)),) if (
                groq_fallback_enabled and groq_model and groq_api_key
            ) else ()
        if len({config.provider for config in fallbacks}) != len(fallbacks):
            raise ValueError("Fallback providers must be distinct")
        self.fallbacks = fallbacks
        self.order = ["openai", *(config.provider for config in fallbacks)]
        self.models: dict[str, str] = {"openai": model}
        self.models.update({config.provider: config.model for config in fallbacks})
        self.fallback_clients: dict[str, Any] = {}
        self.openrouter_upstream = None
        self.groq_model = groq_model
        self.groq = None
        for config in fallbacks:
            if config.provider == "anthropic":
                self.fallback_clients[config.provider] = AnthropicMessages(
                    config.api_key.get_secret_value(), timeout=timeout,
                )
            elif config.provider in {"sambanova", "nvidia", "gemini"}:
                self.fallback_clients[config.provider] = JsonToolEnvelope(
                    config.provider, config.api_key.get_secret_value(), timeout=timeout,
                    output_token_limit=nvidia_output_token_limit if config.provider == "nvidia" else 1024,
                )
            else:
                url = "https://api.groq.com/openai/v1" if config.provider == "groq" else "https://openrouter.ai/api/v1"
                self.fallback_clients[config.provider] = OpenAI(
                    api_key=config.api_key.get_secret_value(), base_url=url, timeout=timeout, max_retries=0,
                )
                if config.provider == "groq":
                    self.groq = self.fallback_clients[config.provider]
                    self.groq_model = config.model
                else:
                    self.openrouter_upstream = config.upstream
        self.cooldown = cooldown if cooldown is not None else RateLimitCooldown()
        self.provider = "openai"
        self.started = False
        self.structured_correction_used = False
        self.attempts: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> dict[str, Any]:
        return self._create(None, **kwargs)

    def create_budgeted(self, charge: Callable[[], None], **kwargs: Any) -> dict[str, Any]:
        """Caller charges the initial request; charge again before a fallback request."""
        return self._create(charge, **kwargs)

    def _create(self, charge: Callable[[], None] | None, **kwargs: Any) -> dict[str, Any]:
        if not self.started:
            if len(self.order) > 1:
                available = [provider for provider in self.order if not self.cooldown.active(provider)]
                if not available:
                    raise ProviderError("PROVIDER_RATE_LIMITED", "Configured providers are cooling down", True)
                self.provider = available[0]
                self.model = self._selected_model()
            self.started = True
        while True:
            try:
                return self._dispatch(charge, **kwargs)
            except APIStatusError as exc:
                # Auth, invalid schemas, policy failures and server errors never trigger a switch.
                if exc.status_code != 429 or len(self.order) == 1:
                    raise
                self.cooldown.limited(exc.response.headers.get("retry-after"), self.provider)
                remaining = self.order[self.order.index(self.provider) + 1:]
                available = [provider for provider in remaining if not self.cooldown.active(provider)]
                if not available:
                    raise
                if charge is not None:
                    charge()  # Includes the existing cancellation/job lease fence before dispatch.
                self.provider = available[0]
                self.model = self._selected_model()

    def _selected_model(self) -> str:
        model = self.groq_model if self.provider == "groq" else self.models[self.provider]
        assert model is not None
        return model

    def _dispatch(self, charge: Callable[[], None] | None, **kwargs: Any) -> dict[str, Any]:
        try:
            return self._request(**kwargs)
        except APIStatusError as exc:
            if not (
                self.provider == "groq" and exc.status_code == 400
                and isinstance(exc.body, dict) and exc.body.get("code") == "json_validate_failed"
                and kwargs.get("text", {}).get("format", {}).get("type") == "json_schema"
            ):
                raise
            if self.structured_correction_used:
                raise ProviderError("MODEL_OUTPUT_INVALID", "Provider rejected structured JSON generation") from exc
            self.structured_correction_used = True
            if charge is not None:
                charge()
            original = portable_input(kwargs["input"])
            items = [{"role": "user", "content": original}] if isinstance(original, str) else original
            feedback = {"role": "user", "content": (
                "Return only JSON satisfying the supplied strict schema, with all required keys and no extra keys. "
                "Preserve the explicitly supplied input values."
            )}
            # One bounded correction; rejected generation and provider prose never enter the next prompt.
            return self._dispatch(charge, **{**kwargs, "input": [*items, feedback]})

    def _request(self, **kwargs: Any) -> dict[str, Any]:
        sdk: Any = self.client if self.provider == "openai" else (
            self.groq if self.provider == "groq" else self.fallback_clients[self.provider]
        )
        assert sdk is not None
        if self.provider == "openai":
            self.cooldown.wait_for_slot(self.min_request_interval_seconds, self.sleep)
            requested_output = kwargs.get("max_output_tokens", self.primary_output_token_limit)
            if isinstance(requested_output, int):
                kwargs = {**kwargs, "max_output_tokens": min(requested_output, self.primary_output_token_limit)}
        if self.provider != "openai":
            # Leave headroom for the complete input/tool schemas on the fallback
            # provider's smaller request budget. Incomplete proposals still fail closed.
            provider_limit = self.nvidia_output_token_limit if self.provider == "nvidia" else 1024
            output_budget = kwargs.get("max_output_tokens", provider_limit)
            if isinstance(output_budget, int):
                kwargs = {**kwargs, "max_output_tokens": min(output_budget, provider_limit)}
            if self.provider == "groq" and self.model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
                # Groq counts reasoning against max_output_tokens. Its documented
                # low effort leaves more of this bounded budget for complete tool arguments.
                # https://console.groq.com/docs/responses-api#reasoning
                kwargs = {**kwargs, "reasoning": {**(kwargs.get("reasoning") or {}), "effort": "low"}}
            if "input" in kwargs:
                kwargs = {**kwargs, "input": portable_input(kwargs["input"])}
        attempt: dict[str, Any] = {"provider": self.provider, "model": self.model, "status": "FAILED"}
        self.attempts.append(attempt)
        try:
            if self.provider in {"anthropic", "sambanova", "nvidia", "gemini"}:
                native = sdk.create(model=self.model, **kwargs)
                attempt["status"] = "SUCCEEDED"
                return cast(dict[str, Any], native)
            if self.provider == "openrouter":
                kwargs = {**kwargs, "extra_body": {"provider": {
                    "only": [self.openrouter_upstream], "allow_fallbacks": False, "require_parameters": True,
                }}}
                # The pinned Responses route rejects the optional parallel flag under
                # require_parameters. Keep strict tools/routing and enforce seriality
                # locally before a response can reach any tool dispatcher.
                if kwargs.get("tools"):
                    kwargs["instructions"] = (kwargs.get("instructions", "")
                                              + "\nReturn exactly one tool call per response.")
                response = sdk.responses.create(model=self.model, store=False, **kwargs)
            else:
                if self.provider == "openai" and self.primary_reasoning_effort is not None:
                    kwargs = {**kwargs, "reasoning": {"effort": self.primary_reasoning_effort}}
                response = sdk.responses.create(model=self.model, store=False, parallel_tool_calls=False, **kwargs)
        except APIStatusError as exc:
            attempt["http_status"] = exc.status_code
            raise
        attempt["status"] = "SUCCEEDED"
        # Tool calls are replayed as API input; use wire names such as "async",
        # rather than SDK-only Python names such as "async_".
        document = cast(dict[str, Any], response.model_dump(mode="json", by_alias=True, exclude_none=True))
        if (self.provider == "openrouter" and kwargs.get("tools")
                and sum(item.get("type") == "function_call" for item in document.get("output", [])) != 1):
            raise ProviderError("MODEL_OUTPUT_INVALID", "Exactly one serial tool call is required")
        return document
