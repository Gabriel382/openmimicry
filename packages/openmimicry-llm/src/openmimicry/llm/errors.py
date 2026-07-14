"""Typed errors for the LLM stack.

Three classes, with a clear `retryable` policy that ``LLMRouter`` reads to
decide whether to attempt a fallback:

* ``LLMTransportError`` — network / 5xx / rate-limit / timeout. Retryable.
* ``LLMAuthError`` — invalid or missing credentials. **Not** retryable; the
  router surfaces this to the caller verbatim.
* ``LLMToolCallError`` — the model returned a tool call that didn't match
  the advertised ``ToolSpec``. Not retryable.

The base class carries `retryable: bool` so consumers (router, telemetry,
health endpoint) can branch on the flag without isinstance ladders.
"""

from __future__ import annotations

__all__ = [
    "LLMAuthError",
    "LLMError",
    "LLMToolCallError",
    "LLMTransportError",
]


class LLMError(Exception):
    """Base class for every typed LLM error."""

    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class LLMTransportError(LLMError):
    """Network / 5xx / rate-limit / timeout. Router will retry."""

    retryable: bool = True


class LLMAuthError(LLMError):
    """Invalid or missing credentials. Surface to the user; never retry."""

    retryable: bool = False


class LLMToolCallError(LLMError):
    """A tool call did not match an advertised ``ToolSpec``."""

    retryable: bool = False
