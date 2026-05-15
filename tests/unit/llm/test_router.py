"""Unit tests for ``LLMRouter``.

Behaviours under test:

* Primary succeeds → fallback is never touched.
* Primary raises ``LLMTransportError`` on the FIRST attempt → router retries.
* Primary exhausts attempts → router yields from the fallback.
* Primary raises ``LLMAuthError`` → router surfaces it (no fallback, no retry).
* Mid-stream transport error after emitting chunks → propagates as-is.
"""

from __future__ import annotations

import pytest
from openmimicry.core.schemas import LLMMessage
from openmimicry.llm import LLMAuthError, LLMRouter, LLMTransportError, MockLLMAdapter
from openmimicry.llm.router import RouterRetryPolicy


def _msgs() -> list[LLMMessage]:
    return [LLMMessage(role="user", content="hi")]


async def _drain(adapter, **kw) -> list[str]:
    out: list[str] = []
    async for chunk in adapter.generate(_msgs(), **kw):
        out.append(chunk.delta)
    return out


async def test_primary_success_skips_fallback() -> None:
    primary = MockLLMAdapter(script=["P"])
    fallback = MockLLMAdapter(script=["F"])
    router = LLMRouter(primary=primary, fallback=fallback)

    out = await _drain(router)
    assert out == ["P", ""]
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0


async def test_primary_retries_before_falling_back() -> None:
    primary = MockLLMAdapter(script=["A"], fail_on=1)
    fallback = MockLLMAdapter(script=["B"])
    router = LLMRouter(
        primary=primary,
        fallback=fallback,
        retry=RouterRetryPolicy(attempts=3, backoff_s=0.0),
    )
    out = await _drain(router)
    # All three primary attempts fail before fallback is tried.
    assert len(primary.calls) == 3
    assert len(fallback.calls) == 1
    assert out == ["B", ""]


async def test_fallback_used_after_transport_error() -> None:
    primary = MockLLMAdapter(script=["X"], fail_on=1)
    fallback = MockLLMAdapter(script=["Y"])
    router = LLMRouter(
        primary=primary,
        fallback=fallback,
        retry=RouterRetryPolicy(attempts=1, backoff_s=0.0),
    )
    out = await _drain(router)
    assert out == ["Y", ""]


async def test_auth_error_is_not_retried_and_no_fallback() -> None:
    primary = MockLLMAdapter(script=["X"], fail_on=1, failure=LLMAuthError)
    fallback = MockLLMAdapter(script=["Y"])
    router = LLMRouter(
        primary=primary,
        fallback=fallback,
        retry=RouterRetryPolicy(attempts=5, backoff_s=0.0),
    )
    with pytest.raises(LLMAuthError):
        await _drain(router)
    assert len(primary.calls) == 1  # no retry
    assert len(fallback.calls) == 0  # no fallback


async def test_no_fallback_re_raises_transport_error() -> None:
    primary = MockLLMAdapter(script=["X"], fail_on=1)
    router = LLMRouter(
        primary=primary,
        fallback=None,
        retry=RouterRetryPolicy(attempts=2, backoff_s=0.0),
    )
    with pytest.raises(LLMTransportError):
        await _drain(router)
    assert len(primary.calls) == 2


async def test_mid_stream_transport_error_propagates_not_retried() -> None:
    """Once a chunk has been delivered to the caller, retry would duplicate."""
    # Primary emits one chunk, then raises on chunk 2.
    primary = MockLLMAdapter(script=["A", "B", "C"], fail_on=2)
    fallback = MockLLMAdapter(script=["F"])
    router = LLMRouter(
        primary=primary,
        fallback=fallback,
        retry=RouterRetryPolicy(attempts=5, backoff_s=0.0),
    )
    deltas: list[str] = []
    with pytest.raises(LLMTransportError):
        async for chunk in router.generate(_msgs()):
            deltas.append(chunk.delta)
    assert deltas == ["A"]
    # Primary was called exactly once (no retry after partial emission).
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0


async def test_router_healthcheck_or_logic() -> None:
    healthy = MockLLMAdapter()
    sick = MockLLMAdapter()
    await sick.close()

    # Primary healthy => True regardless of fallback.
    r1 = LLMRouter(primary=healthy, fallback=sick)
    assert await r1.healthcheck() is True

    # Primary sick, fallback healthy => True.
    r2 = LLMRouter(primary=sick, fallback=MockLLMAdapter())
    assert await r2.healthcheck() is True

    # Both sick => False.
    sick2 = MockLLMAdapter()
    await sick2.close()
    r3 = LLMRouter(primary=sick, fallback=sick2)
    assert await r3.healthcheck() is False


async def test_router_close_closes_both() -> None:
    primary = MockLLMAdapter()
    fallback = MockLLMAdapter()
    router = LLMRouter(primary=primary, fallback=fallback)
    await router.close()
    assert await primary.healthcheck() is False
    assert await fallback.healthcheck() is False
