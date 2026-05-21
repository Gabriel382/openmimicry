---
name: "M4: Sprite2DAvatarAdapter"
about: First concrete AvatarRuntimeAdapter — 2D sprite renderer
title: "[M4] Sprite2DAvatarAdapter + frontend Sprite2D runtime"
labels: ["module", "M4", "avatar", "modality"]
assignees: []
---

## Overview

First concrete avatar modality. Backend adapter + frontend React component, communicating over the wire-protocol projection.

**Parallelism: parallel with M5, M6 (once M3 lands).** Depends on Phase 0, M0, M3.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §2.4, §5, §9
2. [`docs/modules/M4_avatar_sprite2d.md`](../docs/modules/M4_avatar_sprite2d.md)
3. [`docs/character_packs.md`](../docs/character_packs.md)
4. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §1.1
5. [`docs/desktop_overlay.md`](../docs/desktop_overlay.md) §6

## LLM brief

> You are implementing **Module M4 (`Sprite2DAvatarAdapter`)** of OpenMimicry. M3 (`openmimicry-avatar` core) has landed; the Protocol, schemas, pack loader, director, and orchestrator are stable.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §2.4, §5, §9 — `AvatarDirective`, `CharacterPack`, the Protocol, the wire-protocol projection.
> 2. `docs/modules/M4_avatar_sprite2d.md` — this brief.
> 3. `docs/character_packs.md` — frame folder convention, the `emotion + emotion_speaking` fallback rule you must honour.
> 4. `docs/avatar_modalities.md` §1.1 — what Sprite2D is and what fields it ignores by design.
> 5. `docs/desktop_overlay.md` §6 — how the frontend mount node is provisioned.
>
> Implement the 13-step plan. The adapter must accept any well-formed `AvatarDirective` (including fields it doesn't render) without raising. Ignore `gesture`, `gaze`, `intensity` — that is correct behaviour for Sprite2D.
>
> Two pieces of code live in two repos roots: Python at `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/sprite2d/` and TypeScript at `apps/desktop/frontend/src/runtimes/sprite2d/`. They communicate exclusively via the wire protocol defined in `contracts.md` §9.
>
> Constraint: do not import from sibling Python packages other than `openmimicry-core` and your parent `openmimicry-avatar`. The frontend code goes in `apps/desktop/frontend/`; do not touch `apps/desktop/src-tauri` (M8's territory). Open the PR titled `feat(avatar): M4 — Sprite2DAvatarAdapter + frontend runtime` with the Definition-of-done checklist ticked.

## Definition of done

See [`docs/modules/M4_avatar_sprite2d.md`](../docs/modules/M4_avatar_sprite2d.md).
