"""Contract tests for LLMAdapter.

Implementations register themselves under entry-point group
``openmimicry.contracts.llm``. M1 ships two: ``MockLLMAdapter`` and
``LiteLLMAdapter`` (the latter only succeeds the network-touching tests
when LiteLLM is installed; those checks are gated separately).
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import LLMAdapter
from openmimicry.core.schemas import LLMMessage

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
def test_llmadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("no LLMAdapter implementations registered")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, LLMAdapter), f"{name!r} does not satisfy LLMAdapter Protocol"


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("no LLMAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        result = await instance.healthcheck()
        assert isinstance(result, bool)


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_generate_streams_at_least_one_chunk(implementations) -> None:
    """Every adapter must produce at least one LLMChunk ending in a
    terminal finish_reason.

    Adapters that require a live network call (LiteLLMAdapter) are skipped
    when healthcheck() returns False, or when their name != "mock".
    """
    if not implementations:
        pytest.skip("no LLMAdapter implementations registered")
    any_ran = False
    for name, factory in implementations:
        instance = factory()
        if not _is_safe_to_call(instance):
            await instance.close()
            continue
        if not await instance.healthcheck():
            await instance.close()
            continue
        chunks = []
        async for chunk in instance.generate([LLMMessage(role="user", content="ping")]):
            chunks.append(chunk)
            if len(chunks) > 64:
                break
        await instance.close()
        assert chunks, f"{name!r} produced no chunks"
        terminal = next((c for c in chunks if c.finish_reason is not None), None)
        assert terminal is not None, f"{name!r} produced no terminal chunk"
        any_ran = True
    if not any_ran:
        pytest.skip("no hermetic LLMAdapter implementations registered (mock not loaded)")


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_close_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("no LLMAdapter implementations registered")
    for _name, factory in implementations:
        instance = factory()
        await instance.close()
        await instance.close()


def _is_safe_to_call(adapter) -> bool:
    """Only call generate() on adapters that don't need network.

    M1 adapters expose ``name``; the in-process mock is named "mock". Real
    provider adapters (LiteLLMAdapter etc.) are skipped from CI to keep
    the contract suite hermetic.
    """
    return getattr(adapter, "name", "") == "mock"
