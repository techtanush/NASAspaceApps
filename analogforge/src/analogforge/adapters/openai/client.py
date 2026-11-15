"""Bounded Responses routing; separate credentials, explicit models, no SDK retries."""

import math
import threading
import time
from collections.abc import Callable
from typing import Any, cast

from openai import APIStatusError, OpenAI

from analogforge.agents.runtime.provider import ProviderError


def fallback_options(settings: Any) -> dict[str, Any]:
    key = getattr(settings, "groq_api_key", None)
    return {
        "groq_api_key": key.get_secret_value() if key is not None else None,
        "groq_model": getattr(settings, "groq_model", None),
        "groq_fallback_enabled": getattr(settings, "groq_fallback_enabled", False),
    }


class RateLimitCooldown:
    """Share only a deadline across invocations, never prompts or responses."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.until = 0.0
        self.lock = threading.Lock()

    def active(self) -> bool:
        with self.lock:
            return self.clock() < self.until

    def limited(self, retry_after: str | None) -> None:
        try:
            seconds = float(retry_after or "60")
        except ValueError:
            seconds = 60.0
        seconds = min(300.0, max(1.0, seconds)) if math.isfinite(seconds) else 60.0
        with self.lock:
            self.until = max(self.until, self.clock() + seconds)


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
    ) -> None:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_API_KEY is required")
        if not model:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_MODEL is required")
        self.model = model
        self.primary_model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
        if groq_fallback_enabled and not (groq_api_key and groq_model):
            raise ProviderError("PROVIDER_AUTH_FAILED", "Groq fallback requires GROQ_API_KEY and GROQ_MODEL")
        self.groq_model = groq_model
        self.groq = (
            OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1", timeout=timeout, max_retries=0)
            if groq_fallback_enabled else None
        )
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
            if self.groq is not None and self.cooldown.active():
                self.provider = "groq"
                assert self.groq_model is not None
                self.model = self.groq_model
            self.started = True
        try:
            return self._dispatch(charge, **kwargs)
        except APIStatusError as exc:
            # Auth, invalid schemas, policy failures and server errors never trigger a switch.
            if self.provider != "openai" or exc.status_code != 429 or self.groq is None:
                raise
            self.cooldown.limited(exc.response.headers.get("retry-after"))
            if charge is not None:
                charge()
            self.provider = "groq"
            assert self.groq_model is not None
            self.model = self.groq_model
            return self._dispatch(charge, **kwargs)

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
        sdk = self.client if self.provider == "openai" else self.groq
        assert sdk is not None
        if self.provider == "groq":
            # Leave headroom for the complete input/tool schemas on the fallback
            # provider's smaller request budget. Incomplete proposals still fail closed.
            output_budget = kwargs.get("max_output_tokens", 1024)
            if isinstance(output_budget, int):
                kwargs = {**kwargs, "max_output_tokens": min(output_budget, 1024)}
            if self.model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
                # Groq counts reasoning against max_output_tokens. Its documented
                # low effort leaves more of this bounded budget for complete tool arguments.
                # https://console.groq.com/docs/responses-api#reasoning
                kwargs = {**kwargs, "reasoning": {**(kwargs.get("reasoning") or {}), "effort": "low"}}
            if "input" in kwargs:
                kwargs = {**kwargs, "input": portable_input(kwargs["input"])}
        attempt: dict[str, Any] = {"provider": self.provider, "model": self.model, "status": "FAILED"}
        self.attempts.append(attempt)
        try:
            response = sdk.responses.create(model=self.model, store=False, parallel_tool_calls=False, **kwargs)
        except APIStatusError as exc:
            attempt["http_status"] = exc.status_code
            raise
        attempt["status"] = "SUCCEEDED"
        # Tool calls are replayed as API input; use wire names such as "async",
        # rather than SDK-only Python names such as "async_".
        return cast(dict[str, Any], response.model_dump(mode="json", by_alias=True, exclude_none=True))
