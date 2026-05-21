---
name: "M12: ExternalAvatarAdapter"
about: Generic protocol-based bridge to any third-party renderer
title: "[M12] ExternalAvatarAdapter + protocol spec + echo server"
labels: ["module", "M12", "avatar", "modality", "post-v0.2"]
assignees: []
---

## Overview

Fifth and final avatar modality: a documented WebSocket protocol + thin Python bridge that lets any third-party renderer (VTube Studio-like, Blender, Unreal, browser pets, custom prototypes) plug into OpenMimicry.

**Parallelism: post-v0.2.0; parallel with M9, M10, M11.** Depends on Phase 0, M3.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §5, §9
2. [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M12 section
3. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §1.6

## LLM brief

> Implement Module M12 (External avatar adapter) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (M12 section) and `docs/avatar_modalities.md` §1.6. Add the external wire-protocol amendment to `contracts.md` §9. Build the Python adapter, the Node echo server reference implementation, and the `docs/external_runtimes.md` page. The protocol additions must be Stable (not Frozen) for one minor version while we collect feedback. Open the PR `feat(avatar): M12 — ExternalAvatarAdapter + protocol spec + echo server`.

## Definition of done

See [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M12 section.
