# Module M1: `openmimicry-llm`

## Goal (1 line)

Implement `LiteLLMAdapter`, `LLMRouter`, and `MockLLMAdapter` so the rest of the system can call `LLMAdapter.generate(...)` and stream chunks from any provider LiteLLM supports, with a typed fallback path.

## Scope and non-scope

**In scope.**

- `MockLLMAdapter` — scripted, deterministic; the canonical mock other modules consume during development.
- `LiteLLMAdapter` — wraps `litellm.acompletion(..., stream=True)`.
- `LLMRouter` — wraps a primary `LLMAdapter` and an optional fallback; is itself an `LLMAdapter`.
- A small prompt registry (`openmimicry.llm.prompts`) for system prompts that ship with the project.
- Typed errors: `LLMTransportError`, `LLMAuthError`, `LLMToolCallError`.

**Non-scope.**

- The `LLMAdapter` Protocol itself (Phase 0).
- The `EventBus` and `RuntimeStore` (M0).
- LLM tool-calls being dispatched to tasks (M5 + M6 wiring).
- Conversation state management (M6 owns at the request boundary).

## Inputs (immutable, from contracts.md)

- `LLMAdapter` Protocol (`contracts.md` §3, `openmimicry.core.contracts.llm`).
- Schemas: `LLMMessage`, `LLMChunk`, `ToolSpec`, `LLMUsage` (`contracts.md` §3, `openmimicry.core.schemas.llm`).
- `LLMConfig` sub-config from `AppConfig.llm` (`contracts.md` §7, [`../configuration.md`](../configuration.md)).
- `LLMStarted`, `LLMTokenStreamed`, `LLMReplyComplete`, `ErrorEvent` from `RuntimeEvent` (M1 itself does not publish — the backend does — but the schemas are imported for type-checking conformance tests).

## Outputs (this module owns)

```text
packages/openmimicry-llm/
  pyproject.toml
  README.md
  src/openmimicry/llm/
    __init__.py
    base.py                  # re-export of LLMAdapter for convenience
    errors.py                # LLMTransportError, LLMAuthError, LLMToolCallError
    litellm_adapter.py       # LiteLLMAdapter
    router.py                # LLMRouter
    prompts/
      __init__.py
      system_default.txt
      system_personality.j2
    mocks.py                 # MockLLMAdapter (replaces Phase 0 stub)
tests/unit/llm/
  test_litellm_adapter.py    # mocked litellm.acompletion
  test_router.py
  test_prompts.py
tests/contract/test_llm.py   # un-skipped: LiteLLMAdapter + MockLLMAdapter
```

`pyproject.toml` declares optional deps `[litellm]`: `litellm>=1.40`. The package imports `litellm` lazily inside `LiteLLMAdapter` so it can be installed without LiteLLM present (mock-only mode).

## Mock implementations this module provides

```python
# openmimicry.llm.mocks
class MockLLMAdapter:
    name: str = "mock"

    def __init__(self, script: list[str] | None = None, *, finish_reason: str = "stop",
                 fail_on: int | None = None) -> None:
        """`script` is the sequence of deltas to yield. `fail_on=2` raises on the 2nd chunk."""

    async def generate(self, messages, *, stream=True, tools=None,
                       temperature=None, max_tokens=None):
        # Yields one LLMChunk per script entry, then a terminal LLMChunk with finish_reason.

    async def healthcheck(self) -> bool: ...
    async def close(self) -> None: ...
```

`MockLLMAdapter` is the canonical fixture for testing M6 (backend) without LiteLLM.

## Test surface

- **Contract.** `tests/contract/test_llm.py` parametrises over `[MockLLMAdapter(script=["Hi", "!"]), LiteLLMAdapter(model="ollama/llama3.1")]` (the latter is `pytest.mark.skipif(not ollama_available)`). Verifies that any `LLMAdapter`:
  - `generate(messages=[LLMMessage(role="user", content="hi")])` yields at least one `LLMChunk`.
  - The final chunk has a non-None `finish_reason`.
  - `healthcheck()` returns a bool.
  - `close()` is idempotent.
- **Unit.** `LiteLLMAdapter` translates LiteLLM's stream into `LLMChunk` correctly (mock `litellm.acompletion` with an async generator).
- **Unit.** `LLMRouter` falls back to the secondary adapter when the primary raises `LLMTransportError`. Does NOT fall back on `LLMAuthError`.
- **Unit.** Prompt registry loads Jinja2 templates and renders with a `personality` dict.

## Step-by-step plan (atomic, numbered)

1. Create `packages/openmimicry-llm/pyproject.toml`. Name `openmimicry-llm`, version `0.2.0a0`, path dep on `openmimicry-core`, optional dep `[litellm]: ["litellm>=1.40"]`.
2. Replace the Phase 0 stub `mocks.py` with the real `MockLLMAdapter`. Yield one `LLMChunk(delta=s)` per script entry, then a terminal `LLMChunk(delta="", finish_reason="stop", usage=LLMUsage(...))`.
3. Add `errors.py` with `LLMError` base, `LLMTransportError(LLMError, retryable=True)`, `LLMAuthError(LLMError, retryable=False)`, `LLMToolCallError(LLMError)`.
4. Implement `litellm_adapter.py::LiteLLMAdapter`. Constructor takes a `LiteLLMConfig`-shaped dict (model, temperature, max_tokens, api_base, api_key_env, request_timeout_s, retry). Lazy-import `litellm` inside `generate()`. Translate `LLMMessage` → LiteLLM message dict. For tool support: pass `tools` straight through; on tool-call chunks, populate `LLMChunk.tool_calls`. Map LiteLLM exceptions to `LLMTransportError`/`LLMAuthError`.
5. Implement `router.py::LLMRouter`. Holds `primary: LLMAdapter` and `fallback: LLMAdapter | None`. `generate()` tries primary; on `LLMTransportError`, retries `cfg.retry.attempts` times with `cfg.retry.backoff_s`, then yields from `fallback` if present. Emits no events on its own — it returns the chunks; the backend publishes them.
6. Add `prompts/system_default.txt` and `prompts/system_personality.j2`. Implement `prompts/__init__.py::load(name: str, **vars) -> str` using `jinja2`.
7. Add `tests/unit/llm/test_litellm_adapter.py`. Use `unittest.mock.patch("litellm.acompletion")` returning an async generator. Assert chunk translation.
8. Add `tests/unit/llm/test_router.py`. Use two `MockLLMAdapter`s, one configured to raise `LLMTransportError`; assert fallback receives the call.
9. Add `tests/unit/llm/test_prompts.py`.
10. Un-skip `tests/contract/test_llm.py` for `MockLLMAdapter` and `LiteLLMAdapter` (the latter under `skipif`).
11. Register the implementations via `pyproject.toml` entry points `[project.entry-points."openmimicry.contracts.llm"]` so the contract conftest discovers them.
12. Write `packages/openmimicry-llm/README.md` with a 10-line usage example.
13. Update workspace `CHANGELOG.md`.
14. Run `make ci`. Open PR `feat(llm): M1 — LiteLLMAdapter, LLMRouter, MockLLMAdapter`.

## Definition of done (checklist)

- [ ] `from openmimicry.llm import LiteLLMAdapter, LLMRouter, MockLLMAdapter` works.
- [ ] `LiteLLMAdapter(model="ollama/llama3.1").generate(...)` streams chunks when Ollama is running locally (manual smoke; not gated in CI).
- [ ] `MockLLMAdapter(script=["a", "b"])` yields three chunks (two deltas + terminal).
- [ ] `LLMRouter` falls back on `LLMTransportError`, not on `LLMAuthError`.
- [ ] Contract test in `tests/contract/test_llm.py` passes for both `MockLLMAdapter` and `LiteLLMAdapter` (mocked).
- [ ] Coverage ≥ 80% on `openmimicry-llm` source.
- [ ] `scripts/check_imports.py` clean.
- [ ] `CHANGELOG.md` entry added.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M1 (`openmimicry-llm`)** of OpenMimicry. The Protocol and schemas are already frozen.
>
> Read in order:
>
> 1. `docs/contracts.md` §3 — the `LLMAdapter` Protocol and `LLMMessage`/`LLMChunk`/`ToolSpec` schemas.
> 2. `docs/modules/M1_llm.md` — this brief.
> 3. `docs/adapters.md` §1 — surrounding context for routing, fallback, error model.
> 4. The LiteLLM streaming docs at https://github.com/BerriAI/litellm for `acompletion(..., stream=True)`.
>
> Implement the 14-step plan. Use `litellm` (lazy-imported in `LiteLLMAdapter`), `jinja2` for prompt templates. Constraint: do not import from `openmimicry-voice`, `openmimicry-avatar`, `openmimicry-tasks`, or any non-core sibling.
>
> Ship `MockLLMAdapter` early — M6 (backend) and M2 (voice integration tests) depend on it. Register both `MockLLMAdapter` and `LiteLLMAdapter` via the `openmimicry.contracts.llm` entry point so the contract test discovers them.
>
> Open the PR titled `feat(llm): M1 — LiteLLMAdapter, LLMRouter, MockLLMAdapter` with the Definition-of-done checklist ticked.
