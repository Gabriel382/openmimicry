---
name: "M9: ThreeJSAvatarAdapter"
about: Lightweight 3D modality — VRM and glTF rendered inside the Tauri overlay
title: "[M9] ThreeJSAvatarAdapter + frontend Three.js runtime"
labels: ["module", "M9", "avatar", "modality", "post-v0.2"]
assignees: []
---

## Overview

Second avatar modality. VRM and glTF/GLB rendered with Three.js inside the same Tauri overlay window — proves the pluggability story.

**Parallelism: post-v0.2.0; parallel with M10, M11, M12.** Depends on Phase 0, M3, M7.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §5, §9
2. [`docs/modules/M9_avatar_threejs.md`](../docs/modules/M9_avatar_threejs.md)
3. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §1.3, §2
4. [`@pixiv/three-vrm`](https://github.com/pixiv/three-vrm)

## LLM brief

> You are implementing **Module M9 (`ThreeJSAvatarAdapter`)** of OpenMimicry — the second avatar modality after Sprite2D. M3 (avatar core) and M4 (Sprite2D) have landed; the orchestrator can already swap runtimes.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §5, §9 — `AvatarDirective` with its 3D-relevant fields, the Protocol, the wire protocol.
> 2. `docs/modules/M9_avatar_threejs.md` — this brief.
> 3. `docs/avatar_modalities.md` §1.3, §2 — the modality definition and the adapter contract context.
> 4. `@pixiv/three-vrm` docs: https://github.com/pixiv/three-vrm
>
> Implement the 17-step plan. Critical rules:
>
> - The renderer lives **inside** the existing overlay window mount (`<AvatarHost>`'s mount div). Do not open new windows.
> - Pause the RAF loop when the overlay window is hidden (Tauri emits an event).
> - VRM and glTF/GLB share a duck-typed loader interface so the rest of the code doesn't branch.
> - Ignore fields the adapter doesn't support and never raise. Same rule as Sprite2D: an unknown `gesture` is a no-op, not an error.
>
> Open the PR titled `feat(avatar): M9 — ThreeJSAvatarAdapter + frontend Three.js runtime` with the Definition-of-done checklist ticked. Do not touch `apps/desktop/src-tauri/` — M8's territory. Do not modify Sprite2D — that's done.

## Definition of done

See [`docs/modules/M9_avatar_threejs.md`](../docs/modules/M9_avatar_threejs.md).
