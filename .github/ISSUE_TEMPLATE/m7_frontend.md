---
name: "M7: apps/desktop/frontend"
about: React/Vite, overlay/panel routes, WebSocket client, runtime registry
title: "[M7] apps/desktop/frontend — overlay/panel routes, WS client, runtime registry"
labels: ["module", "M7", "frontend"]
assignees: []
---

## Overview

React/Vite application with `/overlay` (transparent avatar host) and `/panel` (interactive UI) routes, a WebSocket client, and a runtime-adapter registry (Sprite2D, Three.js, ...) that mounts the active modality.

**Parallelism: parallel with everything Python.** Only depends on the wire protocol from Phase 0; can start as soon as Phase 0 lands.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §9 — the WebSocket wire protocol
2. [`docs/modules/M7_frontend.md`](../docs/modules/M7_frontend.md)
3. [`docs/architecture.md`](../docs/architecture.md) §9
4. [`docs/desktop_overlay.md`](../docs/desktop_overlay.md) §6

## LLM brief

> You are implementing **Module M7 (`apps/desktop/frontend`)** of OpenMimicry.
>
> Read in order:
>
> 1. `docs/contracts.md` §9 — the WebSocket wire protocol. This is the contract.
> 2. `docs/modules/M7_frontend.md` — this brief.
> 3. `docs/architecture.md` §9 — process and window topology.
> 4. `docs/desktop_overlay.md` §6 — what's pluggable about the renderer mount.
>
> Implement the 20-step plan. Constraints:
>
> - You do **not** implement Sprite2D, Three.js, or any modality renderer. Those live under `apps/desktop/frontend/src/runtimes/<modality>/` and are owned by their respective modules (M4, M9, …). Your job is the **registry** that mounts them and the shell components around them.
> - Type the WS messages against `contracts.md` §9 verbatim. A drift between TS and Python types is the most likely source of bugs; the protocol is the truth.
> - The `WSProvider` must accept an injected socket factory so tests can supply a `MockWebSocket`.
> - Strict TypeScript. No `any`, no `as unknown as` escape hatches.
>
> Open the PR titled `feat(desktop-frontend): M7 — overlay/panel routes, WS client, runtime registry` with the Definition-of-done checklist ticked. Do not touch `apps/desktop/src-tauri/` — that's M8.

## Definition of done

See [`docs/modules/M7_frontend.md`](../docs/modules/M7_frontend.md).
