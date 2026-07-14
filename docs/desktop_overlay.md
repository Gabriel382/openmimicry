# Desktop overlay and click-through

The overlay is the part that makes OpenMimicry feel like a companion: a small, animated character living on top of whatever the user is doing. That character must be visible, draggable, and *not* eat clicks meant for the apps underneath.

This document explains how we achieve that without the most common trap: per-pixel hit-testing on a transparent window.

## 1. Three windows with separated responsibilities

```text
overlay window  - frameless, transparent background, always-on-top,
                  decorations: none, resizable: false
                  permanently click-through in the standard v1.1 layout
                  renders the avatar and speech bubble only

controls window - frameless, always-on-top strip below the avatar
                  interactive drag handle + compact text input
                  moving it moves the avatar window and persists position

panel window    - normal window with decorations
                  carries the text input, voice toggles, conversation history,
                  task cards, settings, debug info
                  hidden by default; tray icon + hotkey open it
```

This split works with Tauri's whole-window click-through behavior: the PNG can
never steal clicks while the separate control strip remains draggable and can
accept keyboard focus. The panel continues to host advanced controls.

## 2. Click-through strategy

We do **not** read alpha values per pixel. Tauri's
`setIgnoreCursorEvents(boolean)` remains a whole-window operation. The v1.1
standard layout keeps the avatar overlay passive and delegates interaction to
the control strip:

- **avatar window:** `ignoreCursorEvents(true)`; all clicks fall through.
- **controls window:** normal cursor events; only its drag handle starts a window
  drag and its text field accepts input.

Toggling is a single Tauri command:

```rust
// src-tauri/src/lib.rs
#[tauri::command]
fn set_overlay_interactive(window: tauri::Window, interactive: bool) {
    let overlay = window.get_webview_window("overlay").unwrap();
    overlay.set_ignore_cursor_events(!interactive).unwrap();
}
```

The legacy interaction toggle remains available for debugging, but normal users
move the companion through the dedicated strip.

## 2.1 Appearance configuration

`config/theme.yml` is the single non-secret appearance file. `GET /appearance`
returns its validated projection to the three frontend routes; the controls
route applies geometry to Tauri. It owns window sizes, colors, avatar scale,
control visibility/gap, and the completed-bubble reading-time formula.

A visual cue (subtle border or glow on the overlay) tells the user which mode they are in. The tray icon and the panel both show the current state.

## 3. Optional "halo" pattern for advanced users

For users who want to keep the overlay always-interactive *and* still click through where the character isn't, we document — but do not implement by default — the "halo" pattern: a small invisible square around the character is interactive, and the rest of the overlay is interaction-free. This is achieved by sizing the overlay window tightly around the avatar plus a configurable padding, not by per-pixel hit-testing. It is a config preset, not a code path.

```yaml
ui:
  overlay:
    fit_to_character: true
    interactive_padding_px: 40
```

The overlay loader resizes the window to `avatar_size + 2 * interactive_padding_px`. Outside the window, clicks reach the desktop. Inside, they reach the avatar. Simple, robust.

## 4. Always-on-top and multi-monitor

- The overlay is created with `alwaysOnTop: true`. The panel is not (so it doesn't fight with focused apps).
- On startup, the overlay window is moved to the *active* monitor and saved-position. If the saved position is off-screen (display unplugged), it snaps back to a default corner.
- Multi-monitor changes (DPI change, monitor disconnect) are handled by listening to Tauri's monitor events and re-clamping the window position.

## 5. Tray and hotkeys

- The tray icon shows a small mood pixel that follows the current `AvatarDirective.emotion`.
- Tray menu: Show panel, Toggle interact, Mute mic, Mute voice, Pause live wake, Quit.
- Global hotkeys (Tauri's `globalShortcut`) are registered for:
  - PTT (configurable, default `Ctrl+Space`).
  - Toggle interact mode (default `Ctrl+Shift+M`).
  - Show/hide panel (default `Ctrl+Shift+O`).

## 6. Renderer is pluggable

The overlay window itself is renderer-agnostic. It hosts a `<div id="avatar-mount">` that the active `AvatarRuntimeAdapter` populates. The shell does not know whether that mount renders a sprite, a Three.js canvas, an `<iframe>` to a VTube-like external runtime, or nothing (when Unity is the active runtime and renders in its own window). The full list of supported modalities lives in [`avatar_modalities.md`](./avatar_modalities.md).

What the shell guarantees, regardless of runtime:

- The mount node is fixed-size, transparent-background, absolutely positioned.
- WebSocket events arrive filtered (`AvatarDirective`, `SpeechBubbleText`, `TranscriptPreview`, `TaskCardEvent`, `SystemNotice`) — the renderer never sees raw bus traffic.
- `AvatarOrchestrator.swap_runtime(...)` is exposed as a Tauri command, so the panel's "Settings → Modality" picker can flip Sprite2D ↔ Three.js without restart.

## 7. Performance posture

- The Sprite2D runtime uses `<img>` sequences via CSS `image-rendering: pixelated` and `transform: translateZ(0)` to push frames to the GPU, with `setInterval` per pack fps (no RAF polling).
- The Three.js runtime uses RAF, an orthographic-friendly camera config from `avatar.runtimes.threejs`, and pauses rendering when the overlay is hidden (Tauri's `focus` events).
- No layout thrash for either: avatar and speech bubble are absolutely positioned, fixed size.
- WebSocket payloads are filtered upstream (only projection events reach the frontend), so the renderer's message handler stays small.

## 8. Why no Electron

We use Tauri because it is markedly smaller (single-digit-MB installers), has first-class always-on-top + transparency + ignoreCursorEvents on Windows and Linux, and lets us reuse the existing Vite+React frontend. The portfolio framing is also clearer: Tauri demonstrates more than another Electron app.

## 9. Known platform quirks (documented honestly)

- **Linux/Wayland**: `setIgnoreCursorEvents` works on most compositors but some (older GNOME builds) ignore it. We document this and provide a fallback "halo" config.
- **Windows**: transparent always-on-top windows can flicker briefly during DPI changes; we re-create the overlay window after a monitor event to recover.
- **Multiple GPUs**: the renderer pins to the integrated GPU when possible for power reasons; users can override via `OPENMIMICRY__UI__OVERLAY__GPU=high`.

These limitations are listed in the README rather than swept under the rug; the project is honest about being a research-grade companion, not a finished product.

## 10. Tests

- `apps/desktop/src-tauri/tests/` (Rust): unit tests for the Tauri commands (`set_overlay_interactive`, `move_to_saved_position`, `swap_avatar_runtime`).
- `apps/desktop/frontend/tests/` (Vitest): per-runtime tests for `Sprite2DAvatarAdapter` and `ThreeJSAvatarAdapter`, plus shell tests for the speech bubble and mount swap, all driven by mock WebSocket events.
- Playwright (optional, gated): smoke-test the panel window with `tauri-driver` if the contributor has it installed.
