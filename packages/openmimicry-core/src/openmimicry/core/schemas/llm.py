"""LLM schemas — frozen Pydantic models.

Source of truth: ``docs/contracts.md`` §3.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "LLMChunk",
    "LLMMessage",
    "LLMUsage",
    "ToolSpec",
]


class LLMMessage(BaseModel):
    """A single message in an LLM conversation."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class ToolSpec(BaseModel):
    """A tool advertisement passed to ``LLMAdapter.generate``."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    parameters: dict  # JSON schema


class LLMUsage(BaseModel):
    """Token accounting for a single LLM call."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMChunk(BaseModel):
    """One streamed delta of an LLM response.

    A non-streaming call yields a single chunk with ``finish_reason`` set.
    """

    model_config = ConfigDict(frozen=True)

    delta: str = ""
    role: Literal["assistant"] = "assistant"
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", None] = None
    tool_calls: list[dict] = []
    usage: LLMUsage | None = None
