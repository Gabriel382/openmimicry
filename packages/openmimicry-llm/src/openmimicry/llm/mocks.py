"""Mock LLM adapter — stub placeholder.

Phase 0 contract freeze ships the import-stable name so that consumers can
write ``from openmimicry.llm.mocks import MockLLMAdapter`` today and have a
loud, debuggable error if they try to instantiate it. The real, scripted
``MockLLMAdapter`` is delivered by **M1**; see ``docs/modules/M1_llm.md``
and ``docs/contracts.md`` §8.

DO NOT add real behaviour here. M1 replaces this file wholesale.
"""

from __future__ import annotations

from typing import Any

__all__ = ["MockLLMAdapter"]


class MockLLMAdapter:
    """Placeholder for the real scripted mock that ships with M1.

    The real signature (per ``contracts.md`` §8) is roughly
    ``MockLLMAdapter(script: list[str] | None = None)`` and the instance
    satisfies ``openmimicry.core.contracts.LLMAdapter``. This stub raises so
    accidental use during P1 wave development is immediately visible.
    """

    name: str = "mock"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "MockLLMAdapter is not implemented yet. "
            "It will be delivered by M1 — see docs/modules/M1_llm.md."
        )
