"""Configured Responses client. No model is guessed and SDK retries are disabled."""

from typing import Any, cast

from openai import OpenAI

from analogforge.agents.runtime.provider import ProviderError


class ResponsesClient:
    def __init__(
        self, api_key: str | None, model: str | None, *, base_url: str | None = None, timeout: float = 30
    ) -> None:
        if not api_key:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_API_KEY is required")
        if not model:
            raise ProviderError("PROVIDER_AUTH_FAILED", "OPENAI_MODEL is required")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

    def create(self, **kwargs: Any) -> dict[str, Any]:
        response = self.client.responses.create(model=self.model, store=False, parallel_tool_calls=False, **kwargs)
        return cast(dict[str, Any], response.model_dump(mode="json"))
