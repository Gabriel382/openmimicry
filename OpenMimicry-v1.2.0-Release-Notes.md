# OpenMimicry v1.2.0 — avatar toolbar and continuous voice

## Delivered

- Top-docked avatar toolbar with drag, persisted position lock, hold-to-talk,
  Auto listen, agent voice, browser settings, exit, and compact text input.
- Removal of the native startup settings panel.
- FastAPI browser dashboard for chat, voice status, pack/runtime settings,
  adapter diagnostics, and replayed task cards.
- VAD-driven continuous listening that does not require a wake phrase.
- PTT coordination that temporarily pauses and restores continuous listening.
- Global `Ctrl+Space` PTT routed to the avatar toolbar.
- `Ctrl+Shift+O`, the toolbar gear, and tray menu open the local dashboard.
- Voice launcher repair for missing RealtimeSTT/RealtimeTTS in the project's
  actual Windows `.venv`.
- Correct mock-versus-real voice status and actionable install hints.

## Compatibility

The `live_wake` mode remains available for wake-name deployments. The new
`continuous_listening` field is additive. Existing `config/theme.yml` files
continue to load; the default toolbar height is now 96 px and it docks above
the avatar.

## Validation

- Python unit/integration suite.
- Frontend typecheck, Vitest suite, and production build.
- Ruff lint/format, JSON/YAML configuration, and character-pack validation.
- Backend dashboard, voice status, appearance, chat, and runtime-swap smoke.

Native Tauri/Rust compilation still requires a machine with the Rust toolchain;
the preparation environment does not provide `cargo` or `rustfmt`.
