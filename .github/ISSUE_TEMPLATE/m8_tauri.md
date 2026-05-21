---
name: "M8: apps/desktop/src-tauri"
about: Two windows, click-through, tray, global hotkeys, IPC commands
title: "[M8] apps/desktop/src-tauri — overlay/panel windows, commands, tray, hotkeys"
labels: ["module", "M8", "desktop", "rust"]
assignees: []
---

## Overview

Tauri shell: overlay + panel windows, whole-window click-through (no per-pixel hit testing), tray icon, global hotkeys.

**Parallelism: parallel with M7** if the command surface is agreed upfront. Depends on no Python module.

## Required reading

1. [`docs/desktop_overlay.md`](../docs/desktop_overlay.md)
2. [`docs/modules/M8_tauri.md`](../docs/modules/M8_tauri.md)
3. Tauri 2.x docs for `set_ignore_cursor_events`, `globalShortcut`, tray

## LLM brief

> You are implementing **Module M8 (`apps/desktop/src-tauri`)** of OpenMimicry.
>
> Read in order:
>
> 1. `docs/desktop_overlay.md` — the click-through, window topology, hotkeys, and tray strategy.
> 2. `docs/modules/M8_tauri.md` — this brief.
> 3. Tauri docs for `set_ignore_cursor_events`, `globalShortcut`, tray API in Tauri 2.x.
>
> Implement the 14-step plan. Critical rules:
>
> - **No per-pixel hit testing.** Whole-window `set_ignore_cursor_events(true|false)` is the only mechanism. `docs/desktop_overlay.md` §2 explains why.
> - Two windows: `overlay` (transparent, always-on-top, click-through default) and `panel` (normal). Do not fight the OS chrome on the panel — let it have its decorations.
> - Hotkeys are global (Tauri `globalShortcut`); they must work even when neither window has focus.
> - The mood pixel in the tray comes from frontend events, not from a direct read of the backend. The frontend subscribes to `avatar.directive` over WS and emits an `avatar.emotion` Tauri event.
>
> `cargo fmt`, `cargo clippy -- -D warnings`, `cargo test` must all pass. Do not touch `apps/desktop/frontend/` (M7's territory) except to consume Tauri commands.
>
> Open the PR titled `feat(desktop-tauri): M8 — overlay/panel windows, commands, tray, hotkeys` with the Definition-of-done checklist ticked.

## Definition of done

See [`docs/modules/M8_tauri.md`](../docs/modules/M8_tauri.md).
