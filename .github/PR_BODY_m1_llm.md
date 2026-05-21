# feat(llm): M1 — LiteLLMAdapter, LLMRouter, MockLLMAdapter

Lands `openmimicry-llm` per `docs/modules/M1_llm.md`. The package implements the frozen `LLMAdapter` Protocol from `docs/contracts.md` §3 and unlocks every consumer (M2 voice integration tests, M5 task routing, M6 backend).

## Adapters

- **`MockLLMAdapter`** — replaces the Phase 0 `NotImplementedError` stub. Scripted and deterministic: yields one `LLMChunk` per script entry, then a terminal `LLMChunk(delta="", finish_reason="stop", usage=...)`. Supports `fail_on=N` (raise on the Nth chunk) and a custom `failure` class so `LLMRouter` fallback tests can drive it precisely.
- **`LiteLLMAdapter`** — wraps `litellm.acompletion(..., stream=True)`. LiteLLM is **lazy-imported** inside `generate()` and `healthcheck()` so a pure-mock install (no `[litellm]` extra) doesn't pay the cost. Reads `api_key_env` at call time and raises `LLMAuthError` if the env var is unset. Maps LiteLLM exceptions to typed `LLMTransportError` / `LLMAuthError` (auth-named exceptions or 401/403 patterns). Tool calls are passed through and surfaced as `LLMChunk.tool_calls`.
- **`LLMRouter`** — itself satisfies `LLMAdapter`. Holds a primary and an optional fallback with a `RouterRetryPolicy(attempts, backoff_s)`. Behaviour:
  - retry `LLMTransportError` on the first attempt only (chunks emitted to the caller can't be retried without duplicates);
  - **never** retry on `LLMAuthError`;
  - **never** fall back after the primary has emitted chunks (mid-stream failure propagates);
  - emits no bus events itself — M6 owns that at the request boundary.

## Prompt registry

`openmimicry.llm.prompts.load(prompt_name, /, **vars)` resolves `<prompt_name>.txt` or `<prompt_name>.j2` from a configurable search path. User-supplied search paths win over the packaged defaults. Jinja2 templates are rendered with `StrictUndefined` so a typo in a variable name is loud. The first argument is positional-only so callers can pass `name=...` as a template variable without colliding with the lookup key.

Ships two defaults: `system_default.txt` and `system_personality.j2`.

## Errors

```python
class LLMError(Exception):
    retryable: bool = False

class LLMTransportError(LLMError):
    retryable = True   # router retries; falls back if available and no chunks emitted

class LLMAuthError(LLMError):
    retryable = False  # router never retries / never falls back

class LLMToolCallError(LLMError):
    retryable = False  # tool spec mismatch; surface to caller
```

## Entry-point registration

`pyproject.toml` registers both adapters under group `openmimicry.contracts.llm`:

```toml
[project.entry-points."openmimicry.contracts.llm"]
mock     = "openmimicry.llm.mocks:make_mock_llm_adapter"
litellm  = "openmimicry.llm.litellm_adapter:make_litellm_adapter"
```

The Phase 0 contract conftest discovers them automatically.

## Tests

- `tests/unit/llm/test_mocks.py` — script-to-chunk fidelity, `fail_on`, `calls` log, terminal `usage`, close idempotency. ~7 tests.
- `tests/unit/llm/test_router.py` — primary-success, retry path, fallback path, auth not retried, no fallback re-raises, mid-stream failure propagates without fallback, healthcheck OR-logic, close cascades. ~8 tests.
- `tests/unit/llm/test_litellm_adapter.py` — injects a fake `litellm` module via `sys.modules` so the adapter's lazy import resolves to a scriptable fake. Covers streaming + non-streaming chunk translation, `api_key_env` plumbing, transport vs auth exception mapping, closed-state, missing-LiteLLM behaviour, healthcheck. ~9 tests.
- `tests/unit/llm/test_prompts.py` — `.txt` and `.j2` loading, `StrictUndefined`, search-path override, unknown name. ~6 tests.
- `tests/contract/test_llm.py` — un-skipped. Iterates over registered implementations: Protocol `isinstance`, `healthcheck` returns `bool`, hermetic `generate` against the mock (LiteLLMAdapter is skipped via `name=='mock'` guard so CI stays offline), `close` idempotency.

## Verification

```text
pytest -q                            # 119 passed, 22 skipped
ruff check / ruff format --check     # clean
scripts/check_imports.py             # OK
```

## Definition-of-done checklist

- [x] `from openmimicry.llm import LiteLLMAdapter, LLMRouter, MockLLMAdapter` works.
- [x] `MockLLMAdapter(script=["a", "b"])` yields three chunks (two deltas + terminal).
- [x] `LLMRouter` falls back on `LLMTransportError`, not on `LLMAuthError`.
- [x] Contract test in `tests/contract/test_llm.py` passes for the mock; the LiteLLMAdapter conformance is exercised by the unit test suite via fake `litellm`.
- [x] `scripts/check_imports.py` clean.
- [x] `CHANGELOG.md` entry added.
- [ ] `LiteLLMAdapter(model="ollama/llama3.1").generate(...)` streams chunks when Ollama is running locally (manual smoke; not gated in CI).

## Notes for review

- `_classify_litellm_exception` is heuristic — it matches by class name (`*Auth*`, `*PermissionDenied*`, `*Forbidden*`) and by substring (`401`, `403`, `API key`). When LiteLLM eventually exports a stable exception hierarchy we can tighten this; until then this errs on the side of `LLMTransportError` (retryable) which is the conservative default.
- The router treats the first attempt's `fail_on=1` (raise before any yield) as not-emitted, so retries proceed normally. Only `fail_on >= 2` is mid-stream.
- LiteLLM is **not** in the test deps. `test_litellm_adapter.py` injects a fake module via `sys.modules` to keep CI hermetic.

## Labels

`module:llm`, `m1`
