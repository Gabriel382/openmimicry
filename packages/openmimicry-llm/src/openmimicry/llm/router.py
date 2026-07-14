"""LLMRouter -- primary + fallback + retry policy, behind LLMAdapter.

The router itself satisfies the LLMAdapter Protocol so it composes
transparently with the rest of the system. Per the brief:

* Retry on LLMTransportError up to retry.attempts times with
  retry.backoff_s seconds between attempts.
* Do NOT retry on LLMAuthError -- surface it to the caller.
* If a fallback adapter is configured and the primary is exhausted, yield
  chunks from the fallback. The fallback is treated identically -- its own
  LLMAuthError is propagated, and its own LLMTransportError is retried
  under the same policy.
* If the primary has already emitted chunks to the caller, do NOT fall
  back -- propagate the error, since the fallback would duplicate output.

The router never publishes bus events itself. That is the backend's job
at the request boundary in M6.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openmimicry.core.schemas import LLMChunk, LLMMessage, ToolSpec

from .errors import LLMAuthError, LLMTransportError

if TYPE_CHECKING:
    from openmimicry.core.contracts import LLMAdapter

__all__ = ["LLMRouter", "RouterRetryPolicy"]


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouterRetryPolicy:
    """Retry policy for LLMTransportError on a single adapter."""

    attempts: int = 2
    backoff_s: float = 1.5


class LLMRouter:
    """Composes a primary LLMAdapter with an optional fallback."""

    name: str = "router"

    def __init__(
        self,
        *,
        primary: LLMAdapter,
        fallback: LLMAdapter | None = None,
        retry: RouterRetryPolicy | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._retry = retry or RouterRetryPolicy()

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        stream: bool = True,
        tools: Sequence[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        return self._dispatch(
            messages=list(messages),
            stream=stream,
            tools=list(tools) if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _dispatch(
        self,
        *,
        messages: list[LLMMessage],
        stream: bool,
        tools: list[ToolSpec] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AsyncIterator[LLMChunk]:
        primary_emitted = False
        try:
            async for chunk in self._try_adapter(
                self._primary,
                messages=messages,
                stream=stream,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                primary_emitted = True
                yield chunk
            return
        except LLMAuthError:
            raise
        except LLMTransportError as primary_err:
            if primary_emitted:
                # Mid-stream failure; caller already saw chunks. Propagate.
                raise
            if self._fallback is None:
                raise
            _log.warning(
                "LLMRouter: primary adapter %r exhausted (%s); trying fallback %r",
                getattr(self._primary, "name", "?"),
                primary_err,
                getattr(self._fallback, "name", "?"),
            )

        # Fallback path. Same retry policy applies to it.
        async for chunk in self._try_adapter(
            self._fallback,
            messages=messages,
            stream=stream,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def _try_adapter(
        self,
        adapter: LLMAdapter,
        *,
        messages: list[LLMMessage],
        stream: bool,
        tools: list[ToolSpec] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AsyncIterator[LLMChunk]:
        """Run a single adapter with retries on transport errors.

        Retries are only applied to a failed *first attempt*: if any chunk
        has been emitted to the caller, retrying would duplicate, so we
        propagate the error verbatim.
        """
        attempts = max(1, self._retry.attempts)
        last_exc: LLMTransportError | None = None
        for attempt in range(1, attempts + 1):
            try:
                emitted = False
                async for chunk in adapter.generate(
                    messages,
                    stream=stream,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    emitted = True
                    yield chunk
                return
            except LLMAuthError:
                raise
            except LLMTransportError as exc:
                if emitted:
                    raise
                last_exc = exc
                _log.info(
                    "LLMRouter: %r attempt %d/%d failed: %s",
                    getattr(adapter, "name", "?"),
                    attempt,
                    attempts,
                    exc,
                )
                if attempt < attempts:
                    await asyncio.sleep(self._retry.backoff_s)
                continue
        assert last_exc is not None
        raise last_exc

    async def healthcheck(self) -> bool:
        prim_ok = bool(await self._primary.healthcheck())
        if self._fallback is None:
            return prim_ok
        return prim_ok or bool(await self._fallback.healthcheck())

    async def close(self) -> None:
        await self._primary.close()
        if self._fallback is not None:
            await self._fallback.close()
