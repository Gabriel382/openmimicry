"""openmimicry-llm: LLM adapter implementations behind ``LLMAdapter``.

Exports:

* ``LLMAdapter`` — the frozen Protocol re-exported for ergonomics.
* ``MockLLMAdapter`` — deterministic scripted mock.
* ``LiteLLMAdapter`` — LiteLLM-backed adapter (lazy import).
* ``LLMRouter`` — primary + fallback + retry composition.
* ``LLMError``, ``LLMTransportError``, ``LLMAuthError``,
  ``LLMToolCallError`` — typed error hierarchy.
* ``prompts.load`` — tiny prompt-template registry.

See docs/contracts.md §3 for the immutable LLMAdapter surface.
"""

from __future__ import annotations

from .base import LLMAdapter
from .errors import LLMAuthError, LLMError, LLMToolCallError, LLMTransportError
from .litellm_adapter import LiteLLMAdapter, LiteLLMSettings
from .mocks import MockLLMAdapter
from .router import LLMRouter, RouterRetryPolicy

__all__ = [
    "LLMAdapter",
    "LLMAuthError",
    "LLMError",
    "LLMRouter",
    "LLMToolCallError",
    "LLMTransportError",
    "LiteLLMAdapter",
    "LiteLLMSettings",
    "MockLLMAdapter",
    "RouterRetryPolicy",
]

__version__ = "0.2.0a0"
