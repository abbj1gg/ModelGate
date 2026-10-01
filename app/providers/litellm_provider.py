from typing import Any

import litellm

from .base import ChatProvider


def read_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)

    return getattr(value, key, default)


class LiteLLMProvider(ChatProvider):
    def __init__(
        self,
        *,
        provider_model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.provider_model = provider_model
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.provider_model,
            "messages": messages,
            "temperature": temperature,
            "timeout": self.timeout,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await litellm.acompletion(**kwargs)

        choices = read_value(response, "choices", [])
        first_choice = choices[0]

        message = read_value(first_choice, "message", {})
        content = read_value(message, "content", "") or ""

        usage = read_value(response, "usage", {}) or {}

        return {
            "content": content,
            "usage": {
                "prompt_tokens": read_value(usage, "prompt_tokens", 0),
                "completion_tokens": read_value(
                    usage,
                    "completion_tokens",
                    0,
                ),
                "total_tokens": read_value(usage, "total_tokens", 0),
            },
        }