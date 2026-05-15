"""Contract tests for ``LLMAdapter``.

Bodies are intentionally ``pytest.skip(...)`` until M1 lands. The fixture
machinery is real: when M1 registers ``LiteLLMAdapter`` under entry-point
group ``openmimicry.contracts.llm``, these tests will iterate over it.
"""

from __future__ import annotations

import pytest
from openmimicry.core.contracts import LLMAdapter

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
def test_llmadapter_protocol_isinstance(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M1 (no LLMAdapter implementations registered)")
    for name, factory in implementations:
        instance = factory()
        assert isinstance(instance, LLMAdapter), f"{name!r} does not satisfy LLMAdapter Protocol"


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_healthcheck_returns_bool(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M1")
    for _name, factory in implementations:
        instance = factory()
        result = await instance.healthcheck()
        assert isinstance(result, bool)


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_generate_streams_at_least_one_chunk(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M1")
    pytest.skip("M1 will provide a stable scripted-mock fixture for this assertion")


@pytest.mark.parametrize("implementations", ["llm"], indirect=True)
async def test_close_is_idempotent(implementations) -> None:
    if not implementations:
        pytest.skip("awaiting M1")
    for _name, factory in implementations:
        instance = factory()
        await instance.close()
        await instance.close()
