"""LLM adapter Protocol.

Source of truth: ``docs/contracts.md`` §3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from ..schemas.llm import LLMChunk, LLMMessage, ToolSpec

__all__ = ["LLMAdapter"]


@runtime_checkable
class LLMAdapter(Protocol):
    """Streamed LLM call surface.

    Concrete adapters live in ``openmimicry-llm``. The avatar/runtime never
    imports a provider client directly — it always goes through this Protocol.
    """

    name: str

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream ``LLMChunk`` values for the given conversation.

        Implementations are async generators. Non-streaming callers consume the
        single terminal chunk; streaming callers iterate the full sequence.
        """
        ...

    async def healthcheck(self) -> bool:
        """Return True if the underlying provider is reachable."""
        ...

    async def close(self) -> None:
        """Release any underlying resources."""
        ...
