from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.providers.base import ChatProvider


class UnsupportedModelError(Exception):
    """Raised when a requested model is not configured."""


class ChatService:
    def __init__(self, providers: dict[str, ChatProvider]) -> None:
        self.providers = providers

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        provider = self.providers.get(model)

        if provider is None:
            raise UnsupportedModelError(f"Unsupported model: {model}")

        result = await provider.complete(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        return {
            "id": f"chatcmpl-{uuid4().hex}",
            "object": "chat.completion",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["content"],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": result["usage"],
        }