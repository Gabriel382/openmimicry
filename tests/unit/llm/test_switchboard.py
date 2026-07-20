from __future__ import annotations

from openmimicry.core import LLMMessage
from openmimicry.llm import LLMSwitchboard, MockLLMAdapter


async def test_switch_affects_next_generation_and_exposes_model() -> None:
    first = MockLLMAdapter(script=["first"])
    second = MockLLMAdapter(script=["second"])
    switchboard = LLMSwitchboard(
        backends={"openrouter": first, "ollama": second},
        models={"openrouter": "openai/gpt-4o-mini", "ollama": "gpt-oss:20b"},
        active="openrouter",
    )

    switchboard.select("ollama")
    text = ""
    async for chunk in switchboard.generate([LLMMessage(role="user", content="hi")]):
        text += chunk.delta

    assert text == "second"
    assert switchboard.active_backend == "ollama"
    assert switchboard.active_model == "gpt-oss:20b"
    assert len(first.calls) == 0
    assert len(second.calls) == 1
