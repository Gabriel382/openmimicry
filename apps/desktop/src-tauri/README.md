# openmimicry-desktop (M8)

The Rust/Tauri shell. Two visually docked windows, one tray icon with a
dynamic mood pixel, and three global hotkeys. Whole-window click-through
via `set_ignore_cursor_events` — no per-pixel hit testing.

## Run it

Make sure the M7 frontend is installed (`pnpm install --frozen-lockfile`
at the repo root). Then:

```bash
# from repo root
make desktop-m8
# equivalent: cd apps/desktop/src-tauri && cargo tauri dev
```

`cargo tauri dev` runs `pnpm --filter @openmimicry/desktop-frontend dev`
automatically (`beforeDevCommand` in `tauri.conf.json`) and the overlay
window opens on top.

## Commands the frontend invokes

| Command                          | Purpose                                                                  |
|----------------------------------|--------------------------------------------------------------------------|
| `set_overlay_interactive`        | Toggle whole-window click-through.                                       |
| `swap_avatar_runtime`            | Emit `avatar.swap_runtime` to the frontend (`/runtime/swap` is the real). |
| `set_position_locked`            | Persist whether the avatar can be moved.                                 |
| `open_backend_dashboard`         | Open the local settings/task board in the default browser.               |
| `move_overlay_to_saved_position` | Restore the overlay to the saved position, clamped to the monitor.       |
| `save_overlay_position`          | Persist the current overlay position.                                    |
| `overlay_info`                   | Read position, interaction, and lock status for the top toolbar.         |
| `quit_app`                       | Exit the app.                                                            |

## Global hotkeys

* `Ctrl+Space` — PTT (press emits `ptt.down`, release emits `ptt.up`).
* `Ctrl+Shift+M` — toggle overlay interactive / click-through.
* `Ctrl+Shift+O` — open the backend dashboard.

## Tray menu

* Open dashboard
* Quit

The mood pixel listens to `avatar.emotion` events that the frontend
emits (subscribed to `avatar.directive` over WS).

## Tests

```bash
cd apps/desktop/src-tauri
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

The unit + integration tests exercise the pure helpers: clamp math,
safe-corner fallback, state save/load roundtrip, emotion-to-colour map,
mood-pixel render shape, and hotkey-spec parsing. Live-window behaviour
(`set_ignore_cursor_events`, hotkey registration) is covered by the
manual smoke step in the M8 brief's Definition of Done.

## Bundles

`cargo tauri build` produces `.msi` + `.exe` (Windows) and `.deb` +
`.AppImage` (Linux) per `tauri.conf.json`'s `bundle.targets`. CI is the
canonical place to run this; local builds need the native toolchain.
