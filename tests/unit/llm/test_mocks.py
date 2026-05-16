"""Unit tests for ``MockLLMAdapter`` — the canonical scripted mock."""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import LLMAdapter
from openmimicry.core.schemas import LLMMessage
from openmimicry.llm.errors import LLMTransportError
from openmimicry.llm.mocks import MockLLMAdapter


def test_mock_satisfies_llm_adapter_protocol() -> None:
    adapter = MockLLMAdapter()
    assert isinstance(adapter, LLMAdapter)


async def test_mock_yields_one_chunk_per_script_entry_plus_terminal() -> None:
    adapter = MockLLMAdapter(script=["Hello", " ", "world"])
    deltas: list[str] = []
    finish_reasons: list[str | None] = []
    async for chunk in adapter.generate([LLMMessage(role="user", content="hi")]):
        deltas.append(chunk.delta)
        finish_reasons.append(chunk.finish_reason)
    # Three deltas + a terminal empty-delta chunk.
    assert deltas == ["Hello", " ", "world", ""]
    # Only the last chunk has a finish_reason.
    assert finish_reasons[:-1] == [None, None, None]
    assert finish_reasons[-1] == "stop"


async def test_mock_records_call_args() -> None:
    adapter = MockLLMAdapter(script=["x"])
    messages = [LLMMessage(role="user", content="hello")]
    async for _ in adapter.generate(messages, temperature=0.4, max_tokens=128):
        pass
    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call["messages"] == messages
    assert call["temperature"] == 0.4
    assert call["max_tokens"] == 128
    assert call["stream"] is True
    assert call["tools"] == []


async def test_mock_fail_on_raises_on_nth_chunk() -> None:
    adapter = MockLLMAdapter(script=["a", "b", "c"], fail_on=2)
    deltas: list[str] = []
    with pytest.raises(LLMTransportError):
        async for chunk in adapter.generate([LLMMessage(role="user", content="x")]):
            deltas.append(chunk.delta)
    # Chunk 1 emitted, chunk 2 raised before yielding.
    assert deltas == ["a"]


async def test_mock_fail_on_first_chunk_raises_immediately() -> None:
    adapter = MockLLMAdapter(script=["a"], fail_on=1)
    with pytest.raises(LLMTransportError):
        async for _ in adapter.generate([LLMMessage(role="user", content="x")]):
            pass


async def test_mock_healthcheck_and_close() -> None:
    adapter = MockLLMAdapter()
    assert await adapter.healthcheck() is True
    await adapter.close()
    assert await adapter.healthcheck() is False
    # close is idempotent
    await adapter.close()


async def test_mock_terminal_usage_is_attached() -> None:
    adapter = MockLLMAdapter(script=["hello"])
    last_chunk = None
    async for chunk in adapter.generate([LLMMessage(role="user", content="x")]):
        last_chunk = chunk
    assert last_chunk is not None
    assert last_chunk.finish_reason == "stop"
    assert last_chunk.usage is not None
    assert last_chunk.usage.completion_tokens == len("hello")
