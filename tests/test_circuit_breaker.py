import pytest

from app.providers.base import ChatProvider
from app.providers.circuit_breaker import (
    CircuitBreakerProvider,
    CircuitOpenError,
    CircuitState,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class SwitchableProvider(ChatProvider):
    def __init__(self, *, should_fail: bool) -> None:
        self.should_fail = should_fail
        self.calls = 0

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, object]:
        self.calls += 1

        if self.should_fail:
            raise TimeoutError("upstream timeout")

        return {
            "content": "ok",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }


@pytest.mark.asyncio
async def test_circuit_opens_after_failure_threshold() -> None:
    clock = FakeClock()
    upstream = SwitchableProvider(should_fail=True)

    circuit = CircuitBreakerProvider(
        provider=upstream,
        failure_threshold=2,
        recovery_timeout_seconds=30,
        clock=clock,
    )

    with pytest.raises(TimeoutError):
        await circuit.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert circuit.state == CircuitState.CLOSED
    assert circuit.failure_count == 1

    with pytest.raises(TimeoutError):
        await circuit.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert circuit.state == CircuitState.OPEN
    assert upstream.calls == 2

    with pytest.raises(CircuitOpenError):
        await circuit.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert upstream.calls == 2


@pytest.mark.asyncio
async def test_circuit_recovers_after_timeout() -> None:
    clock = FakeClock()
    upstream = SwitchableProvider(should_fail=True)

    circuit = CircuitBreakerProvider(
        provider=upstream,
        failure_threshold=1,
        recovery_timeout_seconds=30,
        clock=clock,
    )

    with pytest.raises(TimeoutError):
        await circuit.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert circuit.state == CircuitState.OPEN

    clock.advance(31)
    upstream.should_fail = False

    result = await circuit.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert result["content"] == "ok"
    assert circuit.state == CircuitState.CLOSED
    assert circuit.failure_count == 0


@pytest.mark.asyncio
async def test_success_resets_failure_count() -> None:
    upstream = SwitchableProvider(should_fail=True)

    circuit = CircuitBreakerProvider(
        provider=upstream,
        failure_threshold=2,
        recovery_timeout_seconds=30,
    )

    with pytest.raises(TimeoutError):
        await circuit.complete(
            model="deepseek-chat",
            messages=[],
            temperature=0.2,
        )

    assert circuit.failure_count == 1

    upstream.should_fail = False

    await circuit.complete(
        model="deepseek-chat",
        messages=[],
        temperature=0.2,
    )

    assert circuit.state == CircuitState.CLOSED
    assert circuit.failure_count == 0