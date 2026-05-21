---
name: "M6: apps/backend (assembly)"
about: FastAPI process, wiring.py, WebSocket projection, /health, /chat
title: "[M6] apps/backend — FastAPI process, wiring, WebSocket projection"
labels: ["module", "M6", "backend", "assembly"]
assignees: []
---

## Overview

The assembly module. Wires the five package contracts into a running FastAPI process. `wiring.py` is the **only** file allowed to import concrete adapter classes.

**Parallelism: assembly.** Needs at least the mocks from M1–M5 to be useful. Can be drafted earlier against mocks-only.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) — every Protocol; `§9` is the WebSocket wire protocol
2. [`docs/modules/M6_backend.md`](../docs/modules/M6_backend.md)
3. [`docs/architecture.md`](../docs/architecture.md) §9–§11
4. [`docs/event_flows.md`](../docs/event_flows.md)

## LLM brief

> You are implementing **Module M6 (`apps/backend`)** of OpenMimicry. M0–M5 have landed; every Protocol has at least a mock implementation, plus concrete adapters for LiteLLM, RealtimeSTT, RealtimeTTS, mcp-agent, Claude Code, and Sprite2D.
>
> Read in order:
>
> 1. `docs/contracts.md` — every Protocol and schema. `§9` is the WebSocket wire protocol you must produce and consume.
> 2. `docs/modules/M6_backend.md` — this brief.
> 3. `docs/architecture.md` §9–§11 — process topology, event flows.
> 4. `docs/event_flows.md` — the exact sequences your integration tests must reproduce.
>
> Implement the 14-step plan. Critical rule: **`wiring.py` is the only file in the repo that imports concrete adapter classes.** Every other file in `apps/backend/` uses Protocols from `openmimicry.core.contracts.*`. The CI step `scripts/check_imports.py` has an explicit allowlist for `apps/backend/src/openmimicry_backend/wiring.py`; do not bypass it elsewhere.
>
> The integration tests in `tests/integration/backend/` are the executable spec for end-to-end behaviour. Use the mock adapters from M1–M5 as their fixtures.
>
> Open the PR titled `feat(backend): M6 — FastAPI process, wiring, WebSocket projection` with the Definition-of-done checklist ticked.

## Definition of done

See [`docs/modules/M6_backend.md`](../docs/modules/M6_backend.md).
