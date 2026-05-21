<div align="center">

# OpenMimicry

**An open-source desktop companion: animated 2D/3D avatars, voice, and agentic task runtimes — all behind a frozen contract surface.**

[![CI](https://github.com/ghenrique/openmimicry/actions/workflows/ci.yml/badge.svg)](https://github.com/ghenrique/openmimicry/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ghenrique/openmimicry/actions/workflows/codeql.yml/badge.svg)](https://github.com/ghenrique/openmimicry/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](#requirements)
[![pnpm 11](https://img.shields.io/badge/pnpm-11.x-f69220)](#requirements)
[![Tauri 2](https://img.shields.io/badge/tauri-2.x-24c8db)](apps/desktop/src-tauri)
[![Contracts: frozen](https://img.shields.io/badge/contracts-frozen-success)](docs/contracts.md)

</div>

OpenMimicry is a transparent desktop overlay that connects an animated character to an LLM, a voice stack, and external agentic task runtimes — all swappable, all behind one frozen `AvatarRuntimeAdapter` Protocol. Five avatar modalities ship (Sprite2D, Three.js/VRM, Live3D, Unity bridge, generic External), three task runtimes (Local shell with allowlist, Claude Code CLI, MCP agent), two voice backends (RealtimeSTT/TTS) with mocks for every layer, and an optional MediaPipe-driven vision pipeline that maps hand / body / head gestures to avatar reactions.

---

## Why this exists

Plenty of "AI desktop pet" projects ship one model + one renderer. The hard part — letting people swap the LLM, swap the avatar's renderer (sprite → VRM → Unity → "anything that speaks WebSocket"), swap the task runner, swap the voice engine — is what OpenMimicry exists to make boring. Every adapter sits behind a Protocol that ships as code in `packages/openmimicry-core`; every concrete class is wired in *one* file (`apps/backend/.../wiring.py`); everything else uses Protocol-typed reads.

The result is a portfolio-quality reference for the pattern: contracts as the spine, adapter packages around it, three apps on top.

---

## Highlights

- **5 avatar modalities, 1 Protocol.** Sprite2D · Three.js (VRM/glTF) · Live3D (mouth / idle / gaze drivers over Three.js) · Unity bridge · External (renderer-agnostic WS).
- **3 LLM backends, 1 LLMAdapter.** Mock · LiteLLM (any provider) · LLMRouter (primary + fallback).
- **3 voice paths.** Mock · RealtimeSTT/TTS for real audio · SpeechController owns the single TTS task + barge-in.
- **3 task runtimes + router.** Mock · LocalShell (allowlist-or-reject, audit log) · ClaudeCodeAdapter · MCPAgentAdapter, all behind a capability-based `TaskRouter`.
- **Vision (optional, off by default).** MediaPipe Hands / Pose / Face → gesture + movement classifiers → `AvatarDirective` overrides. Consent-gated. Frames never leave the process.
- **Transparent desktop overlay.** Tauri 2 shell with two windows (overlay, panel), global hotkeys, mood-pixel tray icon, no per-pixel hit testing.
- **Hermetic tests.** Every adapter has a mock that runs with zero optional dependencies. Contract tests parametrise across every registered implementation. ~250 Python tests + Vitest frontend tests + Rust shell tests.

<table>
<tr><td align="center">

**Avatar swap-in-place** — `POST /runtime/swap` flips Sprite2D → Three.js → Live3D → Unity → External without restart. The avatar state survives the swap thanks to `AvatarOrchestrator.swap_runtime`'s visual-state-preservation invariant.

</td></tr>
</table>

---

## Quick start

### Requirements

| Tool | Version |
|------|---------|
| Python | 3.11 or 3.12 |
| Node | 20 LTS or later |
| pnpm | 11.x (`corepack enable` + `corepack prepare pnpm@11.0.0 --activate`) |
| Rust | stable (only for the Tauri desktop shell — `cargo tauri dev` is optional) |
| OS | Linux, macOS, or Windows 10/11 |

### One-command install (everything mocked, no real network)

```bash
# clone + install the workspace + frontend deps
make install PROFILE=basic
```

That installs every Python package in editable mode, pnpm-installs the frontend, and verifies the toolchain via `make doctor`.

### Run it (two terminals)

```bash
# terminal 1 — FastAPI backend on :8000
make backend

# terminal 2 — Vite frontend on :5173 (browser dev)
make frontend
```

Visit `http://localhost:5173/#/panel`. Type a message, watch the avatar move, see task cards stream. Every adapter is mocked by default.

### Run the native desktop shell

```bash
# requires Rust + Tauri prerequisites for your OS:
#   https://tauri.app/v2/guides/getting-started/prerequisites/
make desktop
```

Two windows open: a transparent overlay (always-on-top, click-through by default — `Ctrl+Shift+M` toggles) and the interactive panel (`Ctrl+Shift+O` toggles). `Ctrl+Space` is PTT.

### Docker (backend-only smoke)

```bash
docker compose up backend
# backend on http://localhost:8000, swagger at /docs
```

The compose file also ships a `frontend-dev` service for browser-only testing. The Tauri shell stays out of compose — it needs a real display.

---

## Switch on the good stuff

Every profile is YAML; nothing is required. The defaults run on mocks.

```bash
# real LLM via LiteLLM
make install PROFILE=full
export OPENROUTER_API_KEY=...
OPENMIMICRY_PROFILE=full make backend

# real voice (RealtimeSTT + RealtimeTTS, optional GPU)
make install PROFILE=voice
OPENMIMICRY_PROFILE=voice make backend

# Three.js avatar with a VRM model
# (drop a real VRM at characters/octomimic_vrm/octomimic.vrm — see that pack's README)
make install PROFILE=threejs

# vision (off by default, opt-in, consent-gated)
make install PROFILE=vision
OPENMIMICRY_PROFILE=vision make backend
```

Profile YAML lives in [`config/profiles/`](config/profiles).

---

## Architecture

```
                            ┌────────────────────────────┐
                            │   apps/desktop/src-tauri   │
                            │   ─ overlay (transparent)  │
                            │   ─ panel                  │
                            │   ─ tray + hotkeys         │
                            └─────────────┬──────────────┘
                                          │  Tauri IPC
                            ┌─────────────▼──────────────┐
                            │   apps/desktop/frontend    │
                            │   ─ React + Vite           │
                            │   ─ runtime registry       │
                            │   ─ /overlay  /panel       │
                            └────────┬──────────┬────────┘
                                     │ /ws      │ /api
                                     │          │
                           ┌─────────▼──────────▼─────────┐
                           │      apps/backend (M6)       │
                           │ FastAPI + WebSocket projection│
                           │ wiring.py ← only file allowed │
                           │ to import concrete adapters   │
                           └──────────────┬───────────────┘
                                          │ Protocols
   ┌──────────────┬──────────────┬────────┴────────┬───────────────┬───────────────┐
   │              │              │                 │               │               │
┌──▼────┐ ┌──────▼─────┐ ┌──────▼──────┐ ┌────────▼─────┐ ┌────────▼────────┐ ┌────▼─────┐
│ -llm  │ │   -voice   │ │  -avatar   │ │   -tasks     │ │ -vision (opt)   │ │  -core   │
│Mock + │ │Mock +      │ │Director +  │ │TaskRouter +  │ │MediaPipe Hands /│ │Phase 0   │
│LiteLLM│ │RealtimeSTT │ │5 modalities│ │LocalShell /  │ │Pose / Head +    │ │contracts │
│Router │ │/TTS +      │ │(M3–M12)    │ │ClaudeCode /  │ │gesture +        │ │schemas   │
│       │ │SpeechCtl   │ │            │ │MCPAgent      │ │movement classf.│ │EventBus  │
└───────┘ └────────────┘ └────────────┘ └──────────────┘ └─────────────────┘ └──────────┘
```

The single immutable interface is [`docs/contracts.md`](docs/contracts.md). Any change to a Protocol or schema requires the change-control procedure in §11 — `schema_version` stays at `1` for every additive amendment shipped through v1.0.

### Wire protocol (frontend ↔ backend)

```jsonc
// server → frontend
{ "type": "avatar.directive", "directive": { ... } }
{ "type": "transcript.preview", "text": "...", "is_final": false }
{ "type": "bubble.text", "text": "...", "complete": false }
{ "type": "task.card", "update": { ... } }
{ "type": "system.notice", "level": "info|warn|error", "message": "..." }

// frontend → server
{ "type": "user.text", "text": "..." }
{ "type": "ptt.down" } | { "type": "ptt.up" }
{ "type": "mode.toggle", "key": "live_wake|agent_voice", "value": true }
{ "type": "task.cancel", "handle": { "id": "...", "runtime": "..." } }
```

Full spec: [`docs/contracts.md`](docs/contracts.md) §9. Additive amendments for Three.js / Live3D / Unity / External / vision are documented next to each modality's brief in `docs/modules/`.

---

## Repository layout

```
openmimicry/
├── packages/                       # 6 publishable Python packages
│   ├── openmimicry-core/           # Phase 0 — frozen contracts + schemas + runtime
│   ├── openmimicry-llm/            # M1
│   ├── openmimicry-voice/          # M2
│   ├── openmimicry-avatar/         # M3 (core) + M4 (Sprite2D) + M9 (ThreeJS) + M10 (Live3D)
│   │                               #          + M11 (Unity) + M12 (External)
│   ├── openmimicry-tasks/          # M5
│   └── openmimicry-vision/         # M13 (optional, off by default)
├── apps/
│   ├── backend/                    # M6 — FastAPI process; wiring.py is the assembly point
│   ├── desktop/
│   │   ├── frontend/               # M7 — React + Vite + Vitest
│   │   └── src-tauri/              # M8 — Tauri 2 shell
│   ├── unity-bridge/               # M11 — C# sample for the Unity adapter
│   └── external-echo/              # M12 — reference WS echo server
├── characters/                     # Bundled packs (sprite2d + vrm placeholder)
├── config/
│   └── profiles/                   # basic / voice / threejs / agent / vision / full ...
├── docs/                           # contracts.md + per-module briefs + architecture
├── scripts/                        # doctor, validate_pack, cleanup-legacy (.sh + .ps1)
├── tests/                          # unit + contract + integration
├── docker/                         # Dockerfile.backend, Dockerfile.frontend-dev
├── docker-compose.yml
├── Makefile                        # Linux / macOS / WSL workflow
└── scripts/win/                    # Windows .bat wrappers around the Makefile targets
```

---

## Extend it

Every modality is plug-in:

| Plug point | Entry-point group | Example |
|------------|-------------------|---------|
| LLM adapter | `openmimicry.contracts.llm` | Wire a custom provider behind `LLMAdapter`. |
| STT adapter | `openmimicry.contracts.stt` | Whisper local, Vosk, etc. |
| TTS adapter | `openmimicry.contracts.tts` | Piper, Azure, OpenAI, custom voice. |
| Avatar runtime | `openmimicry.contracts.avatar_runtime` | Add `pixel_pet`, `live2d`, `blender`. |
| Task runtime | `openmimicry.contracts.task_runtime` | OpenClaw, PicoClaw, custom shell. |
| Vision detector | `openmimicry.contracts.vision_detector` | MoveNet pose, holistic, third-party. |
| Vision classifier | `openmimicry.contracts.vision_gesture_classifier` / `..._movement_classifier` | sklearn / ONNX / rule-based. |

Drop a `[project.entry-points."openmimicry.contracts.<group>"]` line in your package's `pyproject.toml` and the workspace picks it up. The contract test parametrises over every registered implementation.

Want to add a whole new modality? Read [`docs/modules/M9_avatar_threejs.md`](docs/modules/M9_avatar_threejs.md) as a worked example — it's 17 numbered steps from "empty package" to "Sprite2D ↔ Three.js live swap working".

---

## Privacy & security posture

- **Local-first.** No cloud is required for any feature; mocks ship everywhere. Adapters that *can* talk to a cloud (LiteLLM, optional vision classifiers) advertise it loudly at startup.
- **Vision is off by default.** `vision.enabled: true` plus a consent acknowledgement (M7 dialog + bus event) is required before the camera opens. Frames never leave the process.
- **`LocalShellAdapter` is allowlist-only.** No substring matching, no `shell=True`, full audit log, SIGTERM→SIGKILL cancel.
- **`ClaudeCodeAdapter` curates the env.** Only `PATH`, `HOME`, and explicit Anthropic env vars are forwarded; an `UNRELATED_SECRET` planted in the parent env is asserted *not* to leak in the test suite.
- **JS supply chain.** pnpm 11 with `minimum-release-age=14`, `block-exotic-subdeps`, and an `ignore-scripts` allowlist. CI runs `pnpm audit` on every PR. Full policy in [`SECURITY.md`](SECURITY.md).

---

## Make targets — the short list

```bash
make help                        # full target list
make install PROFILE=basic       # install workspace + profile extras
make doctor                      # toolchain sanity check
make backend                     # FastAPI on :8000
make frontend                    # Vite on :5173
make desktop                     # cargo tauri dev
make test                        # full pytest + vitest
make ci                          # lint + typecheck + check-imports + test
make docker-up                   # docker compose up backend
make release-preview             # show the v1.0 publish plan (dry run)
```

Windows users: equivalent `.bat` wrappers live in [`scripts/win/`](scripts/win/) (e.g. `scripts\win\install.bat`).

### Cleaning up the legacy tree

If you cloned before v1.0, the prototype directories (`avatar/`, `backend/`, `frontend/`, …) have been retired into `packages/` and `apps/`. Run once:

```bash
bash scripts/cleanup-legacy.sh --apply
# or, on PowerShell:
.\scripts\cleanup-legacy.ps1 -Apply
```

---

## Documentation

- **Architecture & contracts**: [`docs/contracts.md`](docs/contracts.md), [`docs/architecture.md`](docs/architecture.md), [`docs/event_flows.md`](docs/event_flows.md)
- **Per-modality briefs**: [`docs/modules/`](docs/modules/) — one numbered plan per M*
- **Avatar specifics**: [`docs/character_packs.md`](docs/character_packs.md), [`docs/avatar_modalities.md`](docs/avatar_modalities.md), [`docs/desktop_overlay.md`](docs/desktop_overlay.md)
- **Voice modes**: [`docs/voice_modes.md`](docs/voice_modes.md)
- **Tasks**: [`docs/task_delegation.md`](docs/task_delegation.md)
- **External renderers**: [`docs/external_runtimes.md`](docs/external_runtimes.md)
- **Configuration**: [`docs/configuration.md`](docs/configuration.md), [`docs/testing_and_ci.md`](docs/testing_and_ci.md), [`docs/migration.md`](docs/migration.md)
- **Roadmap**: [`ROADMAP.md`](ROADMAP.md)
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)
- **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md), [`MAINTAINERS.md`](MAINTAINERS.md)
- **Security**: [`SECURITY.md`](SECURITY.md)

---

## License

[MIT](LICENSE) — including every bundled character pack unless its `pack.yaml` says otherwise.

---

<sub>Built between Phase 0 (contract freeze) and M13 (vision). Designed to be a long-lived portfolio reference for "contracts-first, adapters-second" architecture.</sub>
