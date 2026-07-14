---
name: "M0: openmimicry-core (runtime services)"
about: EventBus, AppConfig loader, RuntimeStore, structured logging, lifecycle
title: "[M0] openmimicry-core — EventBus, Runtime, config loader, store, logging"
labels: ["module", "M0", "core"]
assignees: []
---

## Overview

Implement the concrete runtime services every other module depends on, behind the Protocols and schemas frozen in Phase 0.

**Parallelism: blocking.** M0 must land before M1, M2, M3, M5 can start integration tests. M7 (frontend) can proceed without M0 since it only depends on the wire protocol.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2 and §7
2. [`docs/modules/M0_core.md`](../docs/modules/M0_core.md)
3. [`docs/configuration.md`](../docs/configuration.md)
4. [`docs/architecture.md`](../docs/architecture.md) §7 and §14

## LLM brief

> You are implementing **Module M0 (`openmimicry-core`)** of OpenMimicry. Phase 0 has already landed — the Protocols and schemas exist as code under `packages/openmimicry-core/src/openmimicry/core/contracts/` and `.../schemas/`. Your job is to add the **concrete runtime services** behind those signatures.
>
> Read these files first, in order:
>
> 1. `docs/contracts.md` §2 and §7 — the frozen interfaces you must satisfy.
> 2. `docs/modules/M0_core.md` — this brief.
> 3. `docs/configuration.md` — the YAML schema and resolution order.
> 4. `docs/architecture.md` §7 and §14 — bus and lifecycle context.
>
> Implement the 13-step plan. Use `pydantic` v2, `pyyaml`, `structlog`, `watchfiles`, and stdlib `asyncio`. No other dependencies.
>
> Constraints: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, or `openmimicry-tasks`. The CI step `scripts/check_imports.py` will reject the PR otherwise. Do not edit anything under `packages/openmimicry-core/src/openmimicry/core/contracts/` or `.../schemas/` — those are frozen. If you find a gap there, stop and ask.
>
> Open the PR titled `feat(core): M0 — EventBus, Runtime, config loader, store, logging` with every Definition-of-done item ticked.

## Definition of done

See [`docs/modules/M0_core.md`](../docs/modules/M0_core.md).

## Acceptance

- [ ] Coverage ≥ 90% on `packages/openmimicry-core/src/openmimicry/core/` excluding `contracts/` and `schemas/`.
- [ ] `make ci` green.
- [ ] `CHANGELOG.md` entry.
