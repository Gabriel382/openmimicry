"""Unit tests for ``LiteLLMAdapter``.

LiteLLM is not a test dependency. We inject a fake ``litellm`` module via
``sys.modules`` so the adapter's lazy import resolves to our scriptable
fake — no real network call, no real LiteLLM in the dependency tree.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from openmimicry.core.schemas import LLMMessage, ToolSpec
from openmimicry.llm import LiteLLMAdapter, LLMAuthError, LLMTransportError


class _FakeMessage:
    def __init__(self, content: str | None = None, tool_calls: list[Any] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(
        self,
        *,
        delta_content: str | None = None,
        message_content: str | None = None,
        finish_reason: str | None = None,
        tool_calls: list[Any] | None = None,
    ) -> None:
        self.delta = _FakeMessage(content=delta_content, tool_calls=tool_calls)
        self.message = _FakeMessage(content=message_content, tool_calls=tool_calls)
        self.finish_reason = finish_reason


class _FakeUsage:
    def __init__(self, prompt: int = 5, completion: int = 7) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion


class _FakeChunk:
    def __init__(
        self,
        *,
        delta_content: str | None = None,
        finish_reason: str | None = None,
        tool_calls: list[Any] | None = None,
        usage: _FakeUsage | None = None,
    ) -> None:
        self.choices = [
            _FakeChoice(
                delta_content=delta_content,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
            )
        ]
        self.usage = usage


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _install_fake_litellm(monkeypatch: pytest.MonkeyPatch, behaviour: dict[str, Any]) -> dict:
    """Inject a fake ``litellm`` module exposing ``acompletion``.

    ``behaviour["mode"]`` is one of:
      * "stream"   — return an async iterable of fake chunks
      * "complete" — return a single fake completion object
      * "raise"    — raise ``behaviour["exception"]`` from ``acompletion``
    """
    captured: dict[str, Any] = {"calls": []}

    async def fake_acompletion(**kwargs):
        captured["calls"].append(kwargs)
        if behaviour["mode"] == "raise":
            raise behaviour["exception"]
        if behaviour["mode"] == "stream":
            return _FakeStream(behaviour["chunks"])
        if behaviour["mode"] == "complete":
            return behaviour["response"]
        raise AssertionError(f"unknown mode: {behaviour['mode']}")

    fake_module = types.SimpleNamespace(acompletion=fake_acompletion)
    monkeypatch.setitem(sys.modules, "litellm", fake_module)  # type: ignore[arg-type]
    return captured


async def test_streaming_translates_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [
        _FakeChunk(delta_content="Hello"),
        _FakeChunk(delta_content=" "),
        _FakeChunk(delta_content="world"),
        _FakeChunk(finish_reason="stop", usage=_FakeUsage()),
    ]
    captured = _install_fake_litellm(monkeypatch, {"mode": "stream", "chunks": chunks})

    adapter = LiteLLMAdapter(model="openrouter/mock", temperature=0.3, max_tokens=64)
    deltas: list[str] = []
    last_chunk = None
    async for chunk in adapter.generate(
        [LLMMessage(role="user", content="hi")],
        tools=[ToolSpec(name="fs.read", description="read a file", parameters={"type": "object"})],
    ):
        deltas.append(chunk.delta)
        last_chunk = chunk

    assert "Hello" in deltas
    assert "world" in deltas
    assert last_chunk is not None
    assert last_chunk.finish_reason == "stop"
    assert last_chunk.usage is not None
    assert last_chunk.usage.total_tokens == 12

    # Verify the call kwargs reached LiteLLM correctly.
    call = captured["calls"][0]
    assert call["model"] == "openrouter/mock"
    assert call["stream"] is True
    assert call["temperature"] == 0.3
    assert call["max_tokens"] == 64
    assert call["messages"] == [{"role": "user", "content": "hi"}]
    assert call["tools"][0]["function"]["name"] == "fs.read"


async def test_non_streaming_yields_single_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = types.SimpleNamespace(
        choices=[_FakeChoice(message_content="full body", finish_reason="stop")],
        usage=_FakeUsage(),
    )
    _install_fake_litellm(monkeypatch, {"mode": "complete", "response": completion})

    adapter = LiteLLMAdapter(model="openrouter/mock")
    chunks = []
    async for chunk in adapter.generate(
        [LLMMessage(role="user", content="hi")],
        stream=False,
    ):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert chunks[0].delta == "full body"
    assert chunks[0].finish_reason == "stop"


async def test_missing_api_key_env_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_litellm(monkeypatch, {"mode": "stream", "chunks": []})
    monkeypatch.delenv("OPENMIMICRY_TEST_KEY", raising=False)
    adapter = LiteLLMAdapter(model="openrouter/mock", api_key_env="OPENMIMICRY_TEST_KEY")
    with pytest.raises(LLMAuthError):
        async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
            pass


async def test_api_key_env_present_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_fake_litellm(
        monkeypatch,
        {"mode": "stream", "chunks": [_FakeChunk(finish_reason="stop")]},
    )
    monkeypatch.setenv("OPENMIMICRY_TEST_KEY", "sk-test-1234")
    adapter = LiteLLMAdapter(model="openrouter/mock", api_key_env="OPENMIMICRY_TEST_KEY")
    async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
        pass
    assert captured["calls"][0]["api_key"] == "sk-test-1234"


async def test_litellm_exception_maps_to_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_litellm(
        monkeypatch,
        {"mode": "raise", "exception": RuntimeError("connection reset by peer")},
    )
    adapter = LiteLLMAdapter(model="openrouter/mock")
    with pytest.raises(LLMTransportError):
        async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
            pass


async def test_litellm_auth_named_exception_maps_to_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuthenticationError(Exception):
        pass

    _install_fake_litellm(
        monkeypatch,
        {"mode": "raise", "exception": FakeAuthenticationError("invalid key")},
    )
    adapter = LiteLLMAdapter(model="openrouter/mock")
    with pytest.raises(LLMAuthError):
        async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
            pass


async def test_close_then_generate_raises_transport() -> None:
    adapter = LiteLLMAdapter(model="openrouter/mock")
    await adapter.close()
    with pytest.raises(LLMTransportError):
        async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
            pass


async def test_missing_litellm_module_raises_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "litellm", raising=False)
    # Force an ImportError on subsequent import by hiding the module name.
    monkeypatch.setattr(
        "openmimicry.llm.litellm_adapter._import_litellm",
        lambda: (_ for _ in ()).throw(LLMTransportError("litellm not installed")),
    )
    adapter = LiteLLMAdapter(model="openrouter/mock")
    with pytest.raises(LLMTransportError):
        async for _ in adapter.generate([LLMMessage(role="user", content="hi")]):
            pass


async def test_healthcheck_without_litellm_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openmimicry.llm.litellm_adapter._import_litellm",
        lambda: (_ for _ in ()).throw(LLMTransportError("litellm not installed")),
    )
    adapter = LiteLLMAdapter(model="openrouter/mock")
    assert await adapter.healthcheck() is False
