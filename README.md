<div align="center">

<img src="docs/assets/openmimicry-icon.png" alt="OpenMimicry — watercolor jester-mask mascot" width="220" />

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

OpenMimicry is a transparent desktop overlay that connects an animated character to an LLM, a voice stack, optional long-term memory, and external agentic task runtimes. Five avatar modalities ship (Sprite2D, Three.js/VRM, Live3D, Unity bridge, generic External), together with isolated Faster-Whisper speech recognition, commercial/system and opt-in community voice providers, and an optional MediaPipe-driven vision pipeline.

---

## Why this exists

Plenty of "AI desktop pet" projects ship one model + one renderer. The hard part — letting people swap the LLM, swap the avatar's renderer (sprite → VRM → Unity → "anything that speaks WebSocket"), swap the task runner, swap the voice engine — is what OpenMimicry exists to make boring. Every adapter sits behind a Protocol that ships as code in `packages/openmimicry-core`; every concrete class is wired in *one* file (`apps/backend/.../wiring.py`); everything else uses Protocol-typed reads.

The result is a portfolio-quality reference for the pattern: contracts as the spine, adapter packages around it, three apps on top.

---

## Highlights

- **5 avatar modalities, 1 Protocol.** Sprite2D · Three.js (VRM/glTF) · Live3D (mouth / idle / gaze drivers over Three.js) · Unity bridge · External (renderer-agnostic WS).
- **3 LLM backends, 1 LLMAdapter.** Mock · LiteLLM (any provider) · LLMRouter (primary + fallback).
- **Fail-safe voice.** Isolated Faster-Whisper input; OS-native commercial-default TTS; community Piper; consent-gated local Chatterbox cloning; and ElevenLabs BYOK. Audio failure never suppresses the text path.
- **Optional memory.** Off by default. Deterministic SQLite needs no memory LLM; Hindsight and independently selected LLM extraction are explicit opt-ins. Raw audio is never stored.
- **3 task runtimes + router.** Mock · LocalShell (allowlist-or-reject, audit log) · ClaudeCodeAdapter · MCPAgentAdapter, all behind a capability-based `TaskRouter`.
- **Vision (optional, off by default).** MediaPipe Hands / Pose / Face → gesture + movement classifiers → `AvatarDirective` overrides. Consent-gated. Frames never leave the process.
- **Transparent desktop companion.** Tauri 2 shell with a click-through avatar, top controls, bottom message composer, global hotkeys, mood-pixel tray icon, and a localhost browser dashboard.
- **Hermetic tests.** Every core adapter has a zero-network mock. Contract, unit, integration, frontend, configuration, and security tests run without audio hardware.

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
| Python | 3.11–3.13 |
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

Visit `http://127.0.0.1:8000/dashboard` for chat, settings, voice diagnostics,
and task cards. Every adapter is mocked by default.

### Run the native desktop shell

```bash
# requires Rust + Tauri prerequisites for your OS:
#   https://tauri.app/v2/guides/getting-started/prerequisites/
make desktop
```

The desktop appears as one companion: a transparent avatar, a top-docked
interactive toolbar, and a message composer underneath. The toolbar provides
drag, position lock, reply scrolling, hold-to-talk, wake-name listening, agent
voice, browser settings, and exit. The three surfaces are separate internally only because
click-through is a whole-window operating-system feature. No native settings
panel opens.

`Ctrl+Space` is hold-to-talk and does not require a name. `Ctrl+Shift+O` opens
the local browser dashboard. Wake listen stays ready but accepts a command only
when its transcript begins with the configured name, `Mimi` by default. Change
the name, recognition aliases, STT quality, and end-of-speech pause in the
dashboard. The stronger CPU default (`medium.en`) is prewarmed in an isolated
worker at startup; `distil-large-v3` is available for compatible NVIDIA GPUs.
Window geometry, colors, avatar scale, and reply reading time remain in
`config/theme.yml`.

The dashboard also shows the exact active LLM model. The OpenRouter voice
profiles start on `openrouter/openai/gpt-oss-20b`; the optional local backend is
Ollama `gpt-oss:20b`. Accepted turns are processed in order and only the last
four completed exchanges are used as conversational context.

Import Sprite2D characters from **Avatar settings → Import character ZIP**.
See [`docs/character_packs.md`](docs/character_packs.md#import-from-the-dashboard)
for the required `pack.yaml` and sprite layout.

For the v1.6 interaction, memory, character, provider, and voice additions, see
the [v1.6 design appendix](docs/design/OpenMimicry-v1.6.0-Appendix.md) and
[acceptance guide](docs/V1.6.0_ACCEPTANCE.md). The proven v1.5.1 Piper launcher
remains available as a community profile.

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

# real voice (isolated Faster-Whisper + Piper, optional NVIDIA acceleration)
make install PROFILE=voice
OPENMIMICRY_PROFILE=voice make backend

# commercially oriented local voice (no Piper dependency)
make install PROFILE=openrouter-commercial
OPENMIMICRY_PROFILE=openrouter-commercial make backend

# free, local, consent-gated voice cloning (large optional ML install)
make install PROFILE=openrouter-chatterbox
OPENMIMICRY_PROFILE=openrouter-chatterbox make backend

# Windows uses the same voice launcher for Piper and Chatterbox. It reads the
# dashboard selection, repairs the matching profile, prewarms it, and starts.
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1

# paid/BYOK voice selected in an ElevenLabs account
make install PROFILE=openrouter-elevenlabs
OPENMIMICRY_PROFILE=openrouter-elevenlabs make backend

# Three.js avatar with a VRM model
# (drop a real VRM at characters/octomimic_vrm/octomimic.vrm — see that pack's README)
make install PROFILE=threejs

# vision (off by default, opt-in, consent-gated)
make install PROFILE=vision
OPENMIMICRY_PROFILE=vision make backend
```

Profile YAML lives in [`config/profiles/`](config/profiles).

The standard Windows voice launcher reads `config/user.yaml`: Piper keeps the
`openrouter-voice` profile, while a dashboard-selected Chatterbox reference
automatically uses `openrouter-chatterbox`. Chatterbox preserves any verified
working CUDA runtime, repairs incomplete Torch triplets when necessary, keeps
Apple MPS on macOS, validates/repairs the real Perth watermark implementation,
and applies the NumPy 2 correction only in its worker.

---

## Architecture

```
                            ┌────────────────────────────┐
                            │   apps/desktop/src-tauri   │
                            │   ─ overlay (transparent)  │
                            │   ─ top toolbar            │
                            │   ─ bottom composer        │
                            │   ─ tray + hotkeys         │
                            └─────────────┬──────────────┘
                                          │  Tauri IPC
                            ┌─────────────▼──────────────┐
                            │   apps/desktop/frontend    │
                            │   ─ React + Vite           │
                            │   ─ runtime registry       │
                            │   ─ /overlay /controls     │
                            │   ─ /composer              │
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
│LiteLLM│ │isolated STT│ │5 modalities│ │LocalShell /  │ │Pose / Head +    │ │contracts │
│Router │ │/TTS +      │ │(M3–M12)    │ │ClaudeCode /  │ │gesture +        │ │schemas   │
│       │ │SpeechCtl   │ │            │ │MCPAgent      │ │movement classf.│ │EventBus  │
└───────┘ └────────────┘ └────────────┘ └──────────────┘ └─────────────────┘ └──────────┘
```

The immutable interfaces live in [`docs/contracts.md`](docs/contracts.md). Configuration schema v2 adds named LLM backends, response presentation, optional memory, clone consent metadata, and distribution profiles. A deterministic in-memory v1→v2 migration preserves old files without rewriting them.

### Wire protocol (frontend ↔ backend)

```jsonc
// server → frontend
{ "type": "avatar.directive", "directive": { ... } }
{ "type": "transcript.preview", "text": "...", "is_final": false }
{ "type": "bubble.text", "text": "...", "complete": false, "reset": false }
{ "type": "conversation.turn", "role": "user|assistant", "source": "text|voice|assistant", "text": "..." }
{ "type": "task.card", "update": { ... } }
{ "type": "system.notice", "level": "info|warn|error", "message": "..." }

// frontend → server
{ "type": "user.text", "text": "..." }
{ "type": "ptt.down" } | { "type": "ptt.up" }
{ "type": "mode.toggle", "key": "continuous_listening|live_wake|agent_voice", "value": true }
{ "type": "task.cancel", "handle": { "id": "...", "runtime": "..." } }
```

Full spec: [`docs/contracts.md`](docs/contracts.md) §9. Additive amendments for Three.js / Live3D / Unity / External / vision are documented next to each modality's brief in `docs/modules/`.

---

## Repository layout

```
openmimicry/
├── packages/                       # 9 publishable Python packages
│   ├── openmimicry-core/           # Foundation — frozen contracts + schemas + runtime
│   ├── openmimicry-llm/            # Cognition — M1
│   ├── openmimicry-voice/          # M2 — source of truth for STT + TTS adapters
│   ├── openmimicry-stt/            # Sensor-layer facade over openmimicry-voice (STT)
│   ├── openmimicry-tts/            # Effector-layer facade over openmimicry-voice (TTS)
│   ├── openmimicry-avatar/         # Effectors — M3/M4/M9/M10/M11/M12 + AvatarDirector
│   ├── openmimicry-tasks/          # Effectors — M5
│   ├── openmimicry-memory/         # Optional SQLite/Hindsight memory
│   └── openmimicry-vision/         # Sensors — M13 (optional, off by default)
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
make release-preview             # show the v1.6.4 publish plan (dry run)
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

- **Layered architecture**: [`docs/architecture/`](docs/architecture/) — the 5-layer mental model (Foundation / Sensors / Cognition / Effectors / Surfaces), one doc per layer, and a [working-independently guide](docs/architecture/working_independently.md) for picking up one package at a time.
- **Architecture & contracts**: [`docs/contracts.md`](docs/contracts.md), [`docs/architecture.md`](docs/architecture.md), [`docs/event_flows.md`](docs/event_flows.md)
- **Per-modality briefs**: [`docs/modules/`](docs/modules/) — one numbered plan per M*
- **Avatar specifics**: [`docs/character_packs.md`](docs/character_packs.md), [`docs/avatar_modalities.md`](docs/avatar_modalities.md), [`docs/desktop_overlay.md`](docs/desktop_overlay.md)
- **Voice modes**: [`docs/voice_modes.md`](docs/voice_modes.md)
- **v1.6 appendix**: [`docs/design/OpenMimicry-v1.6.0-Appendix.md`](docs/design/OpenMimicry-v1.6.0-Appendix.md)
- **v1.6.4 Perth startup repair**: [`OpenMimicry-v1.6.4-Release-Notes.md`](OpenMimicry-v1.6.4-Release-Notes.md)
- **v1.6.3 unified Chatterbox setup**: [`OpenMimicry-v1.6.3-Release-Notes.md`](OpenMimicry-v1.6.3-Release-Notes.md)
- **v1.6.2 Chatterbox reliability**: [`OpenMimicry-v1.6.2-Release-Notes.md`](OpenMimicry-v1.6.2-Release-Notes.md)
- **Memory and voice providers**: [`docs/memory.md`](docs/memory.md), [`docs/voice_providers.md`](docs/voice_providers.md)
- **Licensing profiles**: [`docs/licensing.md`](docs/licensing.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- **Tasks**: [`docs/task_delegation.md`](docs/task_delegation.md)
- **External renderers**: [`docs/external_runtimes.md`](docs/external_runtimes.md)
- **Configuration**: [`docs/configuration.md`](docs/configuration.md), [`docs/testing_and_ci.md`](docs/testing_and_ci.md), [`docs/migration.md`](docs/migration.md)
- **Roadmap**: [`ROADMAP.md`](ROADMAP.md)
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)
- **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md), [`MAINTAINERS.md`](MAINTAINERS.md)
- **Security**: [`SECURITY.md`](SECURITY.md)

---

## License

[MIT](LICENSE) for OpenMimicry's own source. Optional providers, transitive packages, imported character assets, voice models, and cloud services retain their own terms; review [`docs/licensing.md`](docs/licensing.md) before a commercial distribution.

---

<sub>Built between Phase 0 (contract freeze) and M13 (vision). Designed to be a long-lived portfolio reference for "contracts-first, adapters-second" architecture.</sub>
