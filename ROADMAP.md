# Roadmap

OpenMimicry is structured as a sequence of numbered milestones (`MX`,
`M0`..`M13`). Each module ships behind a frozen contract; the same
adapter Protocol covers every implementation past and future.

## v1.0 — shipped

The contract surface in `docs/contracts.md` is frozen. The Phase 0
schemas, every Protocol, every event variant, and the §9 wire
protocol stay stable for the entire 1.x line.

| Milestone | Module | Status |
|-----------|--------|--------|
| Phase 0 | Contract freeze (`packages/openmimicry-core`) | ✅ |
| MX | Tooling baseline (Ruff, pyright, pytest, CI, pnpm hardening) | ✅ |
| M0 | Core runtime (EventBus, Runtime, AppConfig loader, structlog) | ✅ |
| M1 | `openmimicry-llm` — Mock · LiteLLM · LLMRouter + retry/fallback | ✅ |
| M2 | `openmimicry-voice` — Mock · RealtimeSTT · RealtimeTTS + SpeechController | ✅ |
| M3 | `openmimicry-avatar` core — pack loader · Director · Orchestrator | ✅ |
| M4 | Sprite2D modality (Python adapter + React runtime) | ✅ |
| M5 | `openmimicry-tasks` — TaskRouter · LocalShell · ClaudeCode · MCPAgent · intent detector | ✅ |
| M6 | `apps/backend` — FastAPI, wiring, WS projection | ✅ |
| M7 | `apps/desktop/frontend` — React + Vite + Vitest, overlay + panel | ✅ |
| M8 | `apps/desktop/src-tauri` — Tauri 2 shell, tray, hotkeys | ✅ |
| M9 | Three.js avatar modality (VRM + glTF) | ✅ |
| M10 | Live3D modality (mouth / idle / gaze drivers over M9) | ✅ |
| M11 | Unity bridge (Python adapter + sample Unity project) | ✅ |
| M12 | External avatar adapter (generic WS protocol + echo server) | ✅ |
| M13 | `openmimicry-vision` (MediaPipe hand/body/head + plug-in registries) | ✅ |

## Post-v1.0 ideas (open for contributors)

Numbers continue the M-series so contract-amendment PRs reference
matching numbers.

- **M14 — body-pose gesture classifier.** Land a rule-based body
  classifier on top of `BodyPose` (M13 ships the schema + detector;
  classification is the missing piece).
- **M15 — Live2D modality.** Plug-in Live2D Cubism rendering inside the
  existing Three.js scene mount.
- **M16 — Holistic detector.** MediaPipe Holistic (hands + body + face
  in one pass) as a single `LandmarkDetector`.
- **M17 — Cloud LLM provider extras.** Per-provider extras for
  Anthropic, Google, OpenAI, Bedrock, Azure beyond the generic
  LiteLLM path.
- **M18 — Plugin packaging.** A `cookiecutter` template that scaffolds
  a third-party plugin (custom avatar runtime + classifier + LLM
  provider) wired through entry points.
- **M19 — Frontend consent UX.** The vision dialog + indicator dot
  (M13 ships the bus event; M7 owns the UI).
- **M20 — Live demo site.** Static site that runs the frontend
  against a hosted demo backend.

## Non-goals

- Bundling Unity binaries with the Python install.
- Cloud-hosted vision (the local-first posture is intentional;
  third-party adapters that talk to a cloud must log a startup
  warning naming the destination).
- Face-mesh capture by default (privacy posture). A face-mesh detector
  may land as an opt-in plug-in.

## Cadence

OpenMimicry follows semantic versioning. Within 1.x:

- **Patch** (`1.0.1`, …) — bug fixes, doc edits, additive optional
  fields.
- **Minor** (`1.1.0`, …) — new optional modules / adapters / extras.
  Contracts gain additive amendments only.
- **Major** (`2.0.0`) — when (if) a Protocol field actually has to
  change. Migration note + `schema_version` bump in the same PR.
