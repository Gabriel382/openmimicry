---
name: "M1: openmimicry-llm"
about: LiteLLMAdapter, LLMRouter, MockLLMAdapter
title: "[M1] openmimicry-llm — LiteLLMAdapter + LLMRouter + MockLLMAdapter"
labels: ["module", "M1", "llm"]
assignees: []
---

## Overview

Ship the LLM adapter family behind the frozen `LLMAdapter` Protocol.

**Parallelism: parallel with M2, M3, M5, M7.** Depends on Phase 0 and M0.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §3
2. [`docs/modules/M1_llm.md`](../docs/modules/M1_llm.md)
3. [`docs/adapters.md`](../docs/adapters.md) §1
4. [LiteLLM docs](https://github.com/BerriAI/litellm)

## LLM brief

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

## Definition of done

See [`docs/modules/M1_llm.md`](../docs/modules/M1_llm.md).
