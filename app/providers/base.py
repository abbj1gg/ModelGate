from abc import ABC, abstractmethod
from typing import Any


class ChatProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        """Execute a chat completion through a model provider."""
        raise NotImplementedError