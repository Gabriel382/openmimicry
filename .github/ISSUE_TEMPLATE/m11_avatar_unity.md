---
name: "M11: UnityAvatarAdapter (bridge)"
about: Run a separate Unity app as the renderer over WebSocket
title: "[M11] UnityAvatarAdapter + sample bridge"
labels: ["module", "M11", "avatar", "modality", "post-v0.2", "unity"]
assignees: []
---

## Overview

Fourth avatar modality: a Unity application acts as the renderer; OpenMimicry pushes `AvatarDirective`s over WebSocket; Unity drives an Animator on its side. Unity is **optional**; users who don't choose this modality never need it installed.

**Parallelism: post-v0.2.0; parallel with M9, M10, M12.** Depends on Phase 0, M3.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §5, §9
2. [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M11 section
3. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §1.5

## LLM brief

> Implement Module M11 (Unity bridge) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (M11 section), `docs/avatar_modalities.md` §1.5, and the Unity Animator and WebSocket docs. Ship Python adapter + sample Unity project. Do not bundle Unity binaries. Do not modify other modules. Open the PR `feat(avatar): M11 — UnityAvatarAdapter + sample bridge`. The Unity project lives outside the Python packages; CI does not build it (Unity Cloud Build can be added later).

## Definition of done

See [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M11 section.
