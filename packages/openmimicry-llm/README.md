# openmimicry-llm

LLM adapter package for OpenMimicry. Ships:

- `LiteLLMAdapter` — wraps `litellm.acompletion(..., stream=True)` behind `openmimicry.core.contracts.LLMAdapter`. LiteLLM is lazily imported so a pure-mock install does not need it.
- `LLMRouter` — itself an `LLMAdapter`; tries a primary adapter, retries `LLMTransportError`, then yields from an optional fallback. Does NOT retry on `LLMAuthError`.
- `MockLLMAdapter` — scripted, deterministic mock used by every other module's tests.
- A tiny prompt registry (`openmimicry.llm.prompts`) that loads `.txt` and Jinja2 templates from disk.

## Install

```bash
# Just the mock + router + prompts (no provider call possible).
pip install openmimicry-llm

# Plus a real provider stack.
pip install "openmimicry-llm[litellm]"
```

## Usage

```python
import asyncio
from openmimicry.core.schemas import LLMMessage
from openmimicry.llm import LiteLLMAdapter, LLMRouter, MockLLMAdapter

async def main():
    primary = LiteLLMAdapter(model="openrouter/anthropic/claude-3.5-sonnet")
    fallback = LiteLLMAdapter(model="ollama/llama3.1")
    llm = LLMRouter(primary=primary, fallback=fallback)

    messages = [LLMMessage(role="user", content="Say hello.")]
    async for chunk in llm.generate(messages):
        if chunk.delta:
            print(chunk.delta, end="", flush=True)
    await llm.close()

asyncio.run(main())
```

## Errors

| Exception | Retryable? | Meaning |
|---|---|---|
| `LLMTransportError` | yes | Network blip / 5xx / rate limit; router will retry then fall back. |
| `LLMAuthError` | no | Missing or invalid API key; surfaces to the user. |
| `LLMToolCallError` | no | The model returned a tool call but the spec did not match `ToolSpec`. |

## Prompts

```python
from openmimicry.llm.prompts import load
system = load("system_personality", name="Mimi", style="playful")
```

Templates live in `src/openmimicry/llm/prompts/` and are packaged as data files.

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §3 — the immutable `LLMAdapter` protocol.
- [`docs/modules/M1_llm.md`](../../docs/modules/M1_llm.md) — module brief.
- [`docs/adapters.md`](../../docs/adapters.md) §1 — error model, routing, fallback rationale.
