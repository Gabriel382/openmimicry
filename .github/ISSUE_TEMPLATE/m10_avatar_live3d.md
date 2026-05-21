---
name: "M10: Live3DAvatarAdapter"
about: Audio-driven mouth, procedural idle, gaze, intensity blends — on top of M9
title: "[M10] Live3DAvatarAdapter"
labels: ["module", "M10", "avatar", "modality", "post-v0.2"]
assignees: []
---

## Overview

Third avatar modality: a "live" Three.js character with mouth movement from TTS audio, breathing idle, gaze targeting, and intensity-driven expression blending.

**Parallelism: post-v0.2.0; parallel with M9, M11, M12.** Depends on Phase 0, M3, M9.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §2.3, §5, §9
2. [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M10 section
3. [`docs/avatar_modalities.md`](../docs/avatar_modalities.md) §1.4

## LLM brief

> Implement Module M10 (Live3D) of OpenMimicry. Read `docs/modules/post_v0_2_modalities.md` (the M10 section), `docs/modules/M9_avatar_threejs.md`, and `docs/avatar_modalities.md` §1.4. Build on M9 by composition — do not modify the Three.js runtime. The mouth driver is amplitude-based by default. Open the PR `feat(avatar): M10 — Live3DAvatarAdapter`. Skip-conditions: do not introduce ML models; do not touch sibling Python packages other than `openmimicry-core`.

## Definition of done

See [`docs/modules/post_v0_2_modalities.md`](../docs/modules/post_v0_2_modalities.md) — M10 section.
