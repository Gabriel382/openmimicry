# OpenMimicry v1.1.0 desktop stabilization

This source release turns the initial Sprite2D demonstration into a testable
desktop-companion loop.

## Delivered

- Transparent click-through Sprite2D window plus a separate draggable,
  always-on-top message/control strip.
- Saved avatar position and configurable avatar/control/panel geometry.
- `config/theme.yml` for window appearance and reply reading time.
- Completed bubbles remain for a character-based reading interval and replay to
  windows opened later.
- Structured, allow-listed LLM emotion/action cues with safe plain-text fallback.
- Visibly distinct happy Sprite2D animation.
- Functional agent-voice gating, live-wake speech-to-chat, and `Ctrl+Space` PTT.
- OpenRouter plus free local STT/system-TTS Windows profile and launcher.
- Runtime factory registration, current-runtime pack swap, and task cancellation.
- Clear task-panel explanation and safe mock defaults.

## Verification

- Python suite passed.
- Frontend: 15 test files and 86 tests passed.
- TypeScript typecheck and Vite production build passed.
- Character pack validation passed.
- Backend endpoints and Sprite2D runtime swap smoke-tested.

## Known limits

- Three.js/Live3D swaps are now registered, but a compatible 3D character pack
  is still required for meaningful rendering. The bundled OctoMimic pack is 2D.
- Always-on-top applies to normal desktop windows. Exclusive-fullscreen apps,
  Windows secure desktop/UAC, and some platform compositors can supersede it.
- RealtimeSTT/RealtimeTTS installation and microphone permissions remain
  platform-dependent; the first STT run can download a model.
- `basic` and `openrouter-voice` intentionally use mock tasks. Real shell, MCP,
  or Claude Code work requires an explicit task-runtime configuration.
- The avatar window uses whole-window click-through. Per-pixel hit testing is
  intentionally not implemented; interaction lives in the separate strip.
- The native Tauri/Rust compile must be completed on a machine with the Rust
  toolchain installed; the source-only validation environment used for this
  package did not include `cargo` or `rustfmt`.
