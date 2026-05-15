---
name: "M3: openmimicry-avatar (core)"
about: Pack loader, validator, AvatarDirector, AvatarOrchestrator, MockAvatarRuntimeAdapter
title: "[M3] openmimicry-avatar — pack loader, director, orchestrator, mock runtime"
labels: ["module", "M3", "avatar"]
assignees: []
---

## Overview

The substrate every avatar modality plugs into. Ships pack loading, the state machine, the orchestrator, and the canonical mock runtime adapter.

**Parallelism: parallel with M1, M2, M5, M7.** Depends on Phase 0 and M0. Blocks M4 (Sprite2D) and M9 (Three.js).

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §2.4, §5
2. [`docs/modules/M3_avatar_core.md`](../docs/modules/M3_avatar_core.md)
3. [`docs/character_packs.md`](../docs/character_packs.md)
4. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §2, §4
5. [`docs/event_flows.md`](../docs/event_flows.md)

## LLM brief

> You are implementing **Module M3 (`openmimicry-avatar` core)** of OpenMimicry. The Protocols and schemas are frozen.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §2.4, §5 — `AvatarDirective`, `CharacterPack`, the avatar Protocols.
> 2. `docs/modules/M3_avatar_core.md` — this brief.
> 3. `docs/character_packs.md` — pack format, the state-machine table you must implement verbatim, fallback rules.
> 4. `docs/avatar_modalities.md` §2, §4 — how the orchestrator and runtime adapters compose. (You do NOT implement Sprite2D / Three.js here; that's M4 / M9. You only build the substrate.)
> 5. `docs/event_flows.md` — what events you must react to.
>
> Implement the 14-step plan. The state-machine table in `character_packs.md` §4 is the executable spec; reproduce every cell.
>
> Ship `MockAvatarRuntimeAdapter` early — M6 (backend), M4 (Sprite2D), and the integration suite all consume it. Make sure it records `directives_received` so tests can assert sequences.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-tasks`. Only `openmimicry-core`. Open the PR titled `feat(avatar): M3 — pack loader, director, orchestrator, mock runtime` with the Definition-of-done checklist ticked.

## Definition of done

See [`docs/modules/M3_avatar_core.md`](../docs/modules/M3_avatar_core.md).
