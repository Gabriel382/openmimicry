# Module M8: `apps/desktop/src-tauri`

## Goal (1 line)

Ship the Rust/Tauri shell with two windows (transparent always-on-top overlay; normal interactive panel), the IPC commands the frontend depends on, tray icon, and global hotkeys — without ever needing per-pixel hit testing.

## Scope and non-scope

**In scope.**

- `tauri.conf.json` defining two windows: `overlay` (decoration-less, transparent, always-on-top, click-through default) and `panel` (regular).
- Tauri commands: `set_overlay_interactive`, `move_overlay_to_saved_position`, `swap_avatar_runtime`, `show_panel`, `hide_panel`, `quit_app`.
- Tray icon with a mood pixel that follows the latest `AvatarDirective.emotion` plus a context menu (Show Panel, Toggle Interact, Mute Mic, Mute Voice, Pause Live Wake, Quit).
- Global hotkeys via Tauri's `globalShortcut`: PTT (default `Ctrl+Space`), toggle interact (`Ctrl+Shift+M`), show/hide panel (`Ctrl+Shift+O`).
- Window state persistence (position, panel open/closed).
- Bundle configuration for Windows (`.msi`, `.exe`) and Linux (`.AppImage`, `.deb`).

**Non-scope.**

- The React/TypeScript frontend (M7).
- The backend (M6).
- Per-pixel transparency tricks. We use whole-window `setIgnoreCursorEvents` per `docs/desktop_overlay.md` §2.

## Inputs (immutable, from contracts.md)

The Tauri layer talks to the frontend (TypeScript) but not directly to the Python contracts. Its inputs are:

- The Tauri commands the frontend expects (defined in this brief; documented in `docs/desktop_overlay.md` §2 and §5).
- `UIConfig.overlay` and `UIConfig.hotkeys` from [`../configuration.md`](../configuration.md) — read at startup via an HTTP `GET /config` to the backend, or via a small bootstrap file written by the backend on first run.
- The PTT and interact hotkey contracts described in `docs/desktop_overlay.md` §5.

## Outputs (this module owns)

```text
apps/desktop/src-tauri/
  Cargo.toml
  tauri.conf.json
  build.rs
  rustfmt.toml
  icons/
  src/
    main.rs
    lib.rs                  # tauri::Builder + window setup
    commands.rs             # all #[tauri::command] handlers
    overlay.rs              # transparency/click-through helpers
    tray.rs                 # tray icon + menu
    hotkeys.rs              # globalShortcut wiring
    state.rs                # AppState (saved positions, current emotion)
  tests/
    test_commands.rs
    test_overlay.rs
    test_hotkeys.rs
```

## Mock implementations this module provides

None — this module is a native shell.

## Test surface

- **Unit (Rust).** `set_overlay_interactive(true)` calls `set_ignore_cursor_events(false)`; the inverse for `false`. Validated against a mocked window handle.
- **Unit (Rust).** `move_overlay_to_saved_position` clamps to the active monitor's working area; if the saved position is off-screen, returns to a default corner.
- **Unit (Rust).** Mood-pixel mapping: `idle → grey, listening → cyan, thinking → amber, speaking → green, happy → yellow, error → red`.
- **Manual smoke.** Open the desktop app, verify: overlay is transparent + always-on-top, click-through default, hotkey toggles, tray menu works, panel opens.

## Step-by-step plan (atomic, numbered)

1. Audit the existing `src-tauri/`. Move into `apps/desktop/src-tauri/`. Bump Tauri to the latest 2.x.
2. Edit `tauri.conf.json` to define two windows:
   - `overlay`: `decorations: false`, `transparent: true`, `alwaysOnTop: true`, `skipTaskbar: true`, `width: 360`, `height: 360`, `resizable: false`, `url: "/overlay"`.
   - `panel`: `decorations: true`, `transparent: false`, `alwaysOnTop: false`, `width: 480`, `height: 720`, `visible: false`, `url: "/panel"`.
3. Implement `overlay.rs`:
   - `pub fn set_overlay_interactive(window: &Window, interactive: bool)` calls `window.set_ignore_cursor_events(!interactive)`.
   - `pub fn fit_to_character(window: &Window, size: Size, padding: u32)` resizes the overlay window when `ui.overlay.fit_to_character=true`.
   - `pub fn clamp_to_monitor(window: &Window, pos: PhysicalPosition<i32>) -> PhysicalPosition<i32>`.
4. Implement `commands.rs`:
   - `#[tauri::command] fn set_overlay_interactive(app: AppHandle, interactive: bool)`.
   - `#[tauri::command] fn swap_avatar_runtime(app: AppHandle, runtime: String)` (emits an event the frontend hears; the actual swap is initiated by `POST /runtime/swap` to the backend, but the frontend may also want to update the registry locally).
   - `#[tauri::command] fn move_overlay_to_saved_position(app: AppHandle)`.
   - `#[tauri::command] fn show_panel(app: AppHandle)`, `hide_panel`, `quit_app`.
5. Implement `tray.rs` per `docs/desktop_overlay.md` §5. The tray icon is dynamic: subscribe to a small event emitted from the frontend (`emit("avatar.emotion", emotion)`) and re-render the icon when emotion changes (use a tiny SVG with a colored circle).
6. Implement `hotkeys.rs` using Tauri's `globalShortcut`. On `Ctrl+Space` press, emit `ptt.down` event to the overlay window; on release, `ptt.up`. The frontend `WSProvider` forwards both over the WS. On `Ctrl+Shift+M`, toggle `set_overlay_interactive`. On `Ctrl+Shift+O`, toggle panel visibility.
7. Implement `state.rs::AppState` (saved overlay position, current emotion, current runtime name, panel visibility). Persist to disk with `tauri-plugin-store` or a hand-rolled JSON file under the OS data dir.
8. Wire monitor-change events: on `MonitorChange`, re-clamp overlay; on DPI change, briefly hide+show overlay to recover from any flicker.
9. Register Tauri's CSP and capabilities for the WebSocket connection to localhost.
10. Write Rust unit tests using `tauri::test::mock_app()`.
11. Add a short Tauri smoke test using `tauri-driver` (optional, gated behind `feature = "smoke"`).
12. Add `apps/desktop/src-tauri/README.md` with dev instructions (`cargo tauri dev`).
13. Update `CHANGELOG.md`.
14. `make ci`. Open PR `feat(desktop-tauri): M8 — overlay/panel windows, commands, tray, hotkeys`.

## Definition of done (checklist)

- [ ] `cargo tauri dev` opens an overlay (transparent, always-on-top, click-through) and starts with the panel hidden.
- [ ] `Ctrl+Shift+M` toggles overlay click-through. Visible indicator on the overlay changes.
- [ ] `Ctrl+Shift+O` toggles the panel.
- [ ] `Ctrl+Space` press/release fires `ptt.down`/`ptt.up` events to the frontend.
- [ ] Tray icon's mood pixel updates when the frontend emits a new emotion.
- [ ] Overlay position is preserved across restarts.
- [ ] Monitor disconnect snaps the overlay back to a safe corner instead of falling off-screen.
- [ ] `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test` all green.
- [ ] Bundles build via `tauri build` on Windows and Linux runners.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

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
