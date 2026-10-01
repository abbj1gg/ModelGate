from typing import Any

from .base import ChatProvider


class DemoProvider(ChatProvider):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        latest_user_message = next(
            (
                message["content"]
                for message in reversed(messages)
                if message["role"] == "user"
            ),
            "",
        )

        answer = f"ModelGate demo response: {latest_user_message}"
        prompt_text = " ".join(message["content"] for message in messages)

        prompt_tokens = max(1, len(prompt_text) // 4)
        completion_tokens = max(1, len(answer) // 4)

        return {
            "content": answer,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }