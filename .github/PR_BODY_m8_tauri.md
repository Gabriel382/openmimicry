# feat(desktop-tauri): M8 — overlay/panel windows, commands, tray, hotkeys

Implements `docs/modules/M8_tauri.md` against the M7 frontend.

## What lands

### `apps/desktop/src-tauri/`

```
apps/desktop/src-tauri/
  Cargo.toml                 # Tauri 2.x + tauri-plugin-global-shortcut
  build.rs
  rustfmt.toml
  tauri.conf.json            # overlay + panel windows + bundle targets
  capabilities/default.json  # event + window + global-shortcut permissions
  icons/{icon.png,icon.ico}
  src/
    main.rs                  # two-line entry → openmimicry_desktop::run()
    lib.rs                   # tauri::Builder + plugin + commands + setup
    commands.rs              # all #[tauri::command] handlers
    overlay.rs               # set_interactive + clamp_to_monitor + safe_corner
    tray.rs                  # mood-pixel + context menu + event listener
    hotkeys.rs               # PTT + interact + panel-toggle shortcuts
    state.rs                 # AppState + tmp-file-then-rename persistence
  tests/
    test_overlay.rs
    test_state.rs
    test_tray.rs
    test_hotkeys.rs
  README.md
```

### Two windows, no per-pixel hit testing

`tauri.conf.json` declares:

- `overlay` — `transparent: true`, `decorations: false`,
  `alwaysOnTop: true`, `skipTaskbar: true`, `resizable: false`,
  `shadow: false`, `url: "/#/overlay"`.
- `panel` — `decorations: true`, `resizable: true`, `visible: false`,
  `url: "/#/panel"`.

Click-through is whole-window only — `overlay::set_interactive` calls
`window.set_ignore_cursor_events(!interactive)`. Per
`docs/desktop_overlay.md` §2, this is the only mechanism. There is no
per-pixel hit testing anywhere.

### Commands (the surface the frontend invokes)

All `#[tauri::command]`s return `Result<T, String>` so the JS side gets
plain strings on failure.

- `set_overlay_interactive(interactive)` — toggle click-through.
  Persists the new value to `AppState` and emits
  `overlay.interactive` so the panel UI can mirror it.
- `swap_avatar_runtime(runtime)` — record the requested runtime in
  `AppState` and emit `avatar.swap_runtime`; the **actual** swap is
  initiated by `POST /runtime/swap` to the M6 backend (the frontend
  fires both).
- `show_panel` / `hide_panel` — toggle the panel window; persists
  the visibility flag.
- `move_overlay_to_saved_position` — restore the saved position,
  clamped to the active monitor via `overlay::clamp_to_monitor`. If
  no position is saved, returns an error (the caller falls through to
  the OS default).
- `save_overlay_position` — persist `window.outer_position()`.
- `overlay_info` — small status snapshot for the panel UI.
- `quit_app` — clean exit.

### Tray icon

`tray::build_tray` creates the system tray with a context menu (Show
panel, Toggle overlay interact, Mute mic, Mute voice, Pause live wake,
Quit). The non-quit menu items emit Tauri events
(`tray.toggle_interact`, `tray.mute_mic`, `tray.mute_voice`,
`tray.pause_live_wake`) that the frontend can route to the appropriate
backend toggle.

The **mood pixel** comes from frontend events, not the backend.
`tray::emotion_to_color` maps emotions per the brief:

| Emotion                    | Color  |
|----------------------------|--------|
| `idle`, `neutral`          | grey   |
| `listening`                | cyan   |
| `thinking`, `focused`      | amber  |
| `speaking`                 | green  |
| `happy`                    | yellow |
| `error`, `worried`, `angry`, `sad` | red    |

`tray::render_mood_pixel` paints a 16×16 anti-aliased RGBA circle from
the colour. The tray listens to `avatar.emotion` events (emitted by the
frontend on every `avatar.directive`) and calls `tray.set_icon(...)`.

### Global hotkeys

`hotkeys::register_defaults` registers three shortcuts via
`tauri-plugin-global-shortcut`:

- `Ctrl+Space` — press emits `ptt.down`, release emits `ptt.up`. The
  frontend `WSProvider` forwards both messages over WS to the backend
  (`SpeechController.ptt_down/up`).
- `Ctrl+Shift+M` — toggle overlay interactive / click-through.
- `Ctrl+Shift+O` — toggle panel visibility.

`hotkeys::parse_shortcut` is pure (`"ctrl+shift+m"` → `(Modifiers, Code)`)
so the spec parser is unit-tested without spinning up a real plugin
handle.

### Persisted state

`state::AppState` wraps a `Mutex<PersistedState>` and serialises to
`<data_dir>/state.json` via tmp-file-then-rename (`PersistedState`
records: `schema`, `overlay_position`, `emotion`, `runtime`,
`panel_visible`, `interactive`). The startup path loads the file (or
builds a default record). `RunEvent::ExitRequested` and `RunEvent::Exit`
flush before exit. `WindowEvent::Moved` on the overlay updates the
saved position live.

### Tests

`tests/`:

- `test_overlay.rs` — clamp + safe-corner roundtrips that match the
  in-source unit tests; extra coverage for a negative-origin saved
  position on a two-monitor layout.
- `test_state.rs` — save → load roundtrips the full record; repeated
  saves replace the file.
- `test_tray.rs` — colour map matches the brief table; 16×16 RGBA
  buffer shape; unknown emotion falls back to grey.
- `test_hotkeys.rs` — defaults parse; PTT resolves to `Ctrl+Space`;
  whitespace tolerated; `cmd` alias to `Super`.

In-source `#[cfg(test)] mod tests` in `overlay.rs`, `state.rs`,
`tray.rs`, `hotkeys.rs` cover the edge cases (oversized window,
no-monitor case, negative origin, digit keys, etc).

### Makefile

`make desktop-m8` runs `cargo tauri dev` against the new package.
`make desktop-m8-build` produces the bundles. `make desktop-m8-test`
runs `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`.

The legacy `make desktop` (and `src-tauri/`) stay during the
migration.

### Definition of Done

The checklist tracking is in `docs/modules/M8_tauri.md`. The
test-suite checks (`cargo fmt --check`, `cargo clippy`, `cargo test`)
are covered by `make desktop-m8-test`. Live-window items (overlay
transparent, hotkey toggles, tray mood pixel updating) are manual
smoke steps — the M8 brief explicitly treats them that way because
they need a real display server.

## Out of scope

- The frontend (M7). The IPC surface matches `useTauriCommand` from
  M7 verbatim.
- The backend (M6). Tauri talks to it through the frontend's WS / HTTP
  client; nothing in this PR opens a socket to `:8000`.
- Removing the legacy `src-tauri/` tree. That deletion lands in the
  cleanup PR that retires the prototype.

Closes the M8 task.
