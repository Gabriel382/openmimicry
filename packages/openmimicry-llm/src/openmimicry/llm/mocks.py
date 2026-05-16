"""Scripted, deterministic MockLLMAdapter -- the canonical fixture.

Every test that needs an LLMAdapter without a real provider call uses
this mock. M6 (backend), M2 (voice integration), and the contract suite all
depend on it being stable and import-cheap (no LiteLLM import path).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal

from openmimicry.core.schemas import LLMChunk, LLMMessage, LLMUsage, ToolSpec

__all__ = ["MockLLMAdapter", "make_mock_llm_adapter"]


FinishReason = Literal["stop", "length", "tool_calls", "content_filter"]


class MockLLMAdapter:
    """Scripted LLMAdapter that yields a deterministic chunk sequence.

    Parameters:
      script: sequence of delta strings to yield (one LLMChunk per entry).
              Defaults to ["Hello", " from ", "the mock."].
      finish_reason: finish_reason set on the terminal chunk (default "stop").
      fail_on: if set, raise on the Nth chunk (1-indexed). fail_on=1 raises
               immediately before any chunk is yielded.
      failure: exception class to raise when fail_on fires
               (default LLMTransportError).
      usage: LLMUsage attached to the terminal chunk.
      delay_s: optional per-chunk sleep, for cancellation/interruption tests.
    """

    name: str = "mock"

    def __init__(
        self,
        script: list[str] | None = None,
        *,
        finish_reason: FinishReason = "stop",
        fail_on: int | None = None,
        failure: type[BaseException] | None = None,
        usage: LLMUsage | None = None,
        delay_s: float | None = None,
    ) -> None:
        self._script: list[str] = (
            list(script) if script is not None else ["Hello", " from ", "the mock."]
        )
        self._finish_reason: FinishReason = finish_reason
        self._fail_on = fail_on
        self._failure_cls: type[BaseException] = failure or _default_failure()
        self._usage = usage or LLMUsage(
            prompt_tokens=0,
            completion_tokens=sum(len(s) for s in self._script),
            total_tokens=sum(len(s) for s in self._script),
        )
        self._delay_s = delay_s
        self._closed: bool = False
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Return an async iterator of LLMChunk values."""
        self.calls.append(
            {
                "messages": list(messages),
                "stream": stream,
                "tools": list(tools) if tools else [],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self._stream()

    async def _stream(self) -> AsyncIterator[LLMChunk]:
        for idx, delta in enumerate(self._script, start=1):
            if self._fail_on is not None and idx == self._fail_on:
                raise self._failure_cls(f"MockLLMAdapter scripted failure at chunk {idx}")
            if self._delay_s is not None:
                await asyncio.sleep(self._delay_s)
            yield LLMChunk(delta=delta)

        # Terminal chunk: empty delta, finish_reason set, usage attached.
        yield LLMChunk(delta="", finish_reason=self._finish_reason, usage=self._usage)

    async def healthcheck(self) -> bool:
        return not self._closed

    async def close(self) -> None:
        self._closed = True


def _default_failure() -> type[BaseException]:
    """Lazy import of LLMTransportError to avoid an import cycle."""
    from .errors import LLMTransportError

    return LLMTransportError


def make_mock_llm_adapter() -> MockLLMAdapter:
    """Entry-point factory used by the contract conftest."""
    return MockLLMAdapter()
