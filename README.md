<div align="center">

<img src="docs/assets/openmimicry-icon.png" alt="OpenMimicry — watercolor jester-mask mascot" width="220" />

# OpenMimicry

**A local-first desktop companion framework with animated avatars, voice, interchangeable LLMs, memory, and agentic runtimes — connected through stable contracts.**

[![CI](https://github.com/Gabriel382/openmimicry/actions/workflows/ci.yml/badge.svg)](https://github.com/Gabriel382/openmimicry/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Gabriel382/openmimicry/actions/workflows/codeql.yml/badge.svg)](https://github.com/Gabriel382/openmimicry/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/badge/release-v0.5.1_beta-2ea44f)](#current-release-v051)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Windows 11](https://img.shields.io/badge/Windows_11-fully_tested-success)](#validated-release-scope)
[![Linux](https://img.shields.io/badge/Linux-testing_pending-lightgrey)](#validated-release-scope)
[![macOS](https://img.shields.io/badge/macOS-testing_pending-lightgrey)](#validated-release-scope)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](#requirements)
[![pnpm 11](https://img.shields.io/badge/pnpm-11.x-f69220)](#requirements)
[![Tauri 2](https://img.shields.io/badge/tauri-2.x-24c8db)](apps/desktop/src-tauri)

[Current release](#current-release-v051) ·
[Demo](#video-tutorial) ·
[Progress](#development-progress) ·
[Roadmap](#roadmap-and-todo) ·
[Quick start](#quick-start) ·
[Architecture](#architecture) ·
[Documentation](#documentation)

</div>

OpenMimicry is a transparent desktop companion that connects an animated character to local or cloud LLMs, speech recognition, speech synthesis, optional memory, and external task runtimes.

The current validated release is **v0.5.1 beta**. Its reference implementation is a fully working **Sprite2D desktop companion on Windows 11**, with functional **OpenRouter**, **Ollama**, and **Chatterbox** integrations. The ElevenLabs adapter is available but has not yet completed end-to-end validation. Linux and macOS validation remain open.

> [!IMPORTANT]
> OpenMimicry contains a broader modular architecture than the currently validated release surface. Features marked **implemented** exist in the repository, while features marked **validated** have completed the current end-to-end acceptance path.

---

## Video tutorial

A compressed preview can be played directly from this README. For the full-resolution version, watch the tutorial on YouTube:

**[▶ Watch the Full HD OpenMimicry tutorial on YouTube](https://youtu.be/e1IaVpS4Js4)**

<!--
Upload a compressed MP4 smaller than 10 MB by dragging it into the GitHub README editor.
GitHub will generate a URL similar to:
https://github.com/user-attachments/assets/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Replace the placeholder below with that generated URL and keep it on its own line.
-->

PASTE_GITHUB_VIDEO_ATTACHMENT_URL_HERE

---

## Current release: v0.5.1

### Validated release scope

| Area | Status | Current evidence |
|---|---:|---|
| Sprite2D desktop avatar | ✅ Validated | Animated 2D companion, transparent overlay, controls, text interaction, and voice interaction work end to end. |
| OpenRouter | ✅ Validated | Cloud LLM conversations are functional through the configured OpenRouter backend. |
| Ollama | ✅ Validated | Local LLM conversations are functional through Ollama. |
| Chatterbox | ✅ Validated | Local, consent-gated voice synthesis and voice-reference workflow are functional. |
| ElevenLabs | 🟡 Implemented | Provider integration exists, but the complete user flow has not yet been tested. |
| Windows 11 | ✅ Fully tested | Current reference and release-validation platform. |
| Linux | ⏳ Pending | Installation, desktop overlay, audio, and packaging validation remain. |
| macOS | ⏳ Pending | Installation, desktop overlay, audio, Apple Silicon/MPS, and packaging validation remain. |

### What v0.5.1 demonstrates

- A real desktop companion rather than a browser-only chatbot.
- A fully functional Sprite2D character with listening, thinking, speaking, idle, and error states.
- Runtime selection between a cloud LLM through OpenRouter and a local LLM through Ollama.
- Local voice generation with Chatterbox.
- A React frontend, FastAPI backend, and Tauri desktop shell working as one application.
- Contract-driven adapters that keep LLM, voice, avatar, memory, vision, and task implementations replaceable.
- A local-first architecture in which cloud providers are optional rather than mandatory.

### Known limitations

- ElevenLabs has not yet been validated end to end.
- Linux and macOS have not yet completed the release test matrix.
- Sprite2D is the only avatar modality currently presented as release-validated.
- Other avatar, vision, task, and memory modules should be treated as implemented or experimental until their acceptance paths are completed.
- Packaging, signing, SBOM generation, and reproducible release evidence are still being hardened.

---

## Why this exists

Many desktop-companion projects combine one model, one voice engine, and one renderer into a tightly coupled application. OpenMimicry is designed around the opposite idea: every major capability should be replaceable.

A user or developer should be able to change:

- OpenRouter to Ollama or another LLM provider;
- Sprite2D to VRM, Live3D, Unity, or an external renderer;
- Chatterbox to a system voice or ElevenLabs;
- the memory implementation;
- the task runtime;
- the input and vision stack;

without rebuilding the entire application.

Every adapter sits behind a Protocol defined in `packages/openmimicry-core`. Concrete implementations are assembled in one backend wiring layer, while the rest of the project depends on stable interfaces.

---

## Highlights

- **Working 2D desktop companion.** Sprite2D is the v0.5.1 reference modality and is fully validated on Windows 11.
- **Local or cloud reasoning.** Ollama and OpenRouter are both functional and selectable without changing the UI architecture.
- **Functional local voice.** Chatterbox provides a free, local, consent-gated voice path.
- **Voice providers remain replaceable.** ElevenLabs and other TTS implementations use the same contract, even when their validation status differs.
- **Fail-safe text path.** A speech failure must not suppress or erase the assistant's text response.
- **Optional memory.** Long-term memory is disabled by default and remains independent from the primary conversation model.
- **Transparent desktop surface.** The Tauri shell provides an always-on-top avatar, controls, message composer, tray integration, and global shortcuts.
- **Contract-first architecture.** LLMs, STT, TTS, avatars, tasks, memory, and vision are isolated behind adapter protocols.
- **Mock-first testing.** Core paths can run without paid providers, microphone hardware, or network access.

---

## Development progress

Status legend: **✅ validated**, **🟢 implemented**, **🟡 partial / validation pending**, **⏳ planned**.

| Track | Result | Status | Next acceptance step |
|---|---|---:|---|
| Contract surface and schemas | Core events, protocols, configuration models, and adapter boundaries | 🟢 Implemented | Keep public contracts and version claims synchronized across releases. |
| Core runtime | Event bus, runtime state, configuration, logging, and lifecycle foundations | 🟢 Implemented | Complete trace propagation, bounded shutdown, cancellation, and redaction evidence. |
| LLM layer | Mock, LiteLLM/OpenRouter, Ollama selection, and routing foundations | ✅ Validated for OpenRouter and Ollama | Validate fallback behavior, provider conformance, and failure recovery. |
| Voice input/output | Isolated speech pipeline, Chatterbox, provider profiles, and speech control | ✅ Chatterbox validated on Windows 11 | Test ElevenLabs and complete Linux/macOS audio validation. |
| Sprite2D avatar | Pack loading, avatar director, orchestrator, React renderer, and desktop integration | ✅ Validated | Add automated visual-state and imported-pack acceptance tests. |
| Desktop application | FastAPI backend, WebSocket projection, React/Vite UI, and Tauri shell | ✅ Validated on Windows 11 | Validate Linux/macOS behavior and build distributable installers. |
| Additional avatar modalities | Three.js/VRM, Live3D, Unity bridge, and generic external runtime | 🟢 Implemented in the repository | Run end-to-end modality-specific acceptance and asset/license checks. |
| Memory | Optional local SQLite and external-memory adapters | 🟡 Implemented, broader validation pending | Validate retention, export, failure isolation, and settings UX. |
| Agentic tasks | Task router and local/external runtime adapters | 🟡 Implemented, hardening pending | Centralize approval, policy enforcement, constraints, and audit behavior. |
| Vision | MediaPipe-oriented detector/classifier package and event contracts | 🟡 Implemented, product integration pending | Complete desktop consent, active-camera indication, and end-to-end wiring. |
| Release engineering | CI, CodeQL, tests, versioned documentation, and release workflow foundations | 🟡 In progress | Align version metadata, add fresh-clone evidence, platform matrix, SBOM, signing, and artifact hashes. |

### Release progression

| Stage           | Main objective                                                                           |             State |
| --------------- | ---------------------------------------------------------------------------------------- | ----------------: |
| v0.1.x          | Establish the protocol-oriented core and a basic text runtime                            |       ✅ Completed |
| v0.2.x          | Add speech contracts and the first voice loop                                            |       ✅ Completed |
| v0.3.x          | Add avatar contracts, character packs, and Sprite2D behavior                             |       ✅ Completed |
| v0.4.x          | Integrate the backend, frontend, and native desktop surfaces                             |       ✅ Completed |
| **v0.5.1 beta** | Validate the complete 2D companion with OpenRouter, Ollama, and Chatterbox on Windows 11 | ✅ Current release |
| v0.6.x          | Implement and validate 3D avatar support                                                 |            ⏳ Next |
| v0.7.x          | Complete provider and cross-platform validation                                          |         ⏳ Planned |
| v0.8.x          | Add parallel task execution and orchestration                                            |         ⏳ Planned |
| **v1.0.0**      | Deliver a fully tested, stable, coherent, cross-platform release                         |         🎯 Target |


---

## Roadmap and TODO

This table intentionally separates completed implementation from the evidence still required for a reliable public release.

| Priority | Work item | Status | Definition of done |
|---:|---|---:|---|
| P0 | Validate ElevenLabs | ⏳ | Configure a real account and voice, synthesize several sequential turns, test interruption/recovery, and document limitations and cost behavior. |
| P0 | Test Linux | ⏳ | Fresh install, backend, frontend, Tauri overlay, microphone, STT, Chatterbox/system TTS, Ollama, OpenRouter, shutdown, and restart all pass. |
| P0 | Test macOS | ⏳ | Fresh install, Apple Silicon/Intel compatibility, Tauri overlay, microphone permissions, STT, Chatterbox/MPS or CPU fallback, Ollama, OpenRouter, and restart all pass. |
| P0 | Align version metadata | ⏳ | README, `pyproject.toml`, JavaScript packages, Tauri metadata, changelog, roadmap, tags, and release artifacts all report the same version. |
| P0 | Add fresh-clone acceptance | ⏳ | A clean Windows 11 machine can install and launch the validated profile from the documented commands without manual source edits. |
| P1 | Cross-platform packaging | ⏳ | Produce installable Windows, Linux, and macOS artifacts with documented signing/notarization status. |
| P1 | Task safety and approval gate | 🟡 | Every external write or privileged action is authorized through one centralized policy and exact-plan approval path. |
| P1 | Runtime integrity | 🟡 | Turns have correlated IDs, deterministic cancellation, bounded timeouts, one terminal result, and clean reverse-order shutdown. |
| P1 | Vision product integration | 🟡 | Camera capture remains opt-in, consent blocks startup, and a persistent indicator is visible while capture is active. |
| P1 | Diagnostics and support evidence | 🟡 | Health endpoints, doctor output, redacted logs, platform reports, test counts, and artifact hashes are captured per release. |
| P1 | Accessibility | ⏳ | Keyboard navigation, captions, contrast, scaling, and screen-reader behavior have documented acceptance checks. |
| P2 | Validate 3D and external avatar modes | ⏳ | Three.js/VRM, Live3D, Unity, and external WebSocket renderers pass their own end-to-end test scenarios. |
| P2 | Third-party plugin template | ⏳ | Contributors can scaffold an adapter package, register it through entry points, and run the conformance suite. |
| P2 | Public demo and documentation site | ⏳ | A lightweight public demo and versioned docs explain the validated surface without implying experimental features are stable. |
| P2 | Release supply-chain evidence | ⏳ | Publish checksums, SBOM, provenance, license report, migration notes, and reproducibility information. |

The detailed implementation roadmap remains available in [`ROADMAP.md`](ROADMAP.md). Larger architectural and security work should follow the dependency order: safety first, runtime integrity second, extensibility third, product integration fourth, and release evidence last.

---

## Quick start

### Requirements

| Tool | Version / status |
|---|---|
| Python | 3.11–3.13 |
| Node | 20 LTS or later |
| pnpm | 11.x (`corepack enable` and `corepack prepare pnpm@11.0.0 --activate`) |
| Rust | Stable, required for the native Tauri shell |
| Windows | Windows 11 is the validated v0.5.1 platform |
| Linux | Supported by the architecture, release testing pending |
| macOS | Supported by the architecture, release testing pending |

### Clone the project

```bash
git clone https://github.com/Gabriel382/openmimicry.git
cd openmimicry
```

### Mock/developer installation

This profile runs without paid APIs or external model providers.

```bash
make install PROFILE=basic
make doctor
```

Run the backend and browser frontend in two terminals:

```bash
# terminal 1
make backend

# terminal 2
make frontend
```

Open `http://127.0.0.1:8000/dashboard` for the local dashboard.

### Windows 11: validated OpenRouter + Chatterbox path

```powershell
# From the repository root
.\scripts\win\install.bat openrouter-chatterbox

# Keep provider secrets outside the repository
$env:OPENROUTER_API_KEY = "your-key-here"

# Start the supported Windows voice workflow
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The launcher validates the selected voice profile, prepares the isolated workers, prewarms the required models, and starts the backend. Open the dashboard to configure the active model, character, voice, personality, and interaction mode.

### Ollama

Install Ollama, start its local service, and make the desired model available. The current default local model is:

```bash
ollama pull gpt-oss:20b
```

Select Ollama and the local model from the OpenMimicry dashboard. The Ollama path is functional in v0.5.1.

### Native desktop shell

```bash
make desktop
```

The desktop appears as one companion composed of three coordinated transparent surfaces:

1. the avatar overlay;
2. the top control bar;
3. the message composer.

They are separate windows internally because click-through behavior is controlled at the operating-system window level.

Default shortcuts:

| Shortcut | Action |
|---|---|
| `Ctrl+Space` | Hold-to-talk |
| `Ctrl+Shift+M` | Toggle avatar-window interaction |
| `Ctrl+Shift+O` | Open the local dashboard |

### Docker backend smoke test

```bash
docker compose up backend
```

The backend is exposed on `http://localhost:8000`, with API documentation at `/docs`. The native Tauri shell is intentionally not included in Docker because it requires a real desktop display.

---

## Configuration profiles

Profiles live in [`config/profiles/`](config/profiles/).

| Profile | Purpose | v0.5.1 validation status |
|---|---|---:|
| `basic` | Fully mocked local development | ✅ |
| `openrouter-voice` | OpenRouter with the standard voice path | ✅ Windows |
| `openrouter-chatterbox` | OpenRouter with local Chatterbox voice | ✅ Windows |
| `openrouter-commercial` | OpenRouter with commercially oriented/system voice dependencies | 🟡 |
| `openrouter-elevenlabs` | OpenRouter with ElevenLabs BYOK | ⏳ Not yet tested |
| `vision` | Optional MediaPipe-oriented vision pipeline | 🧪 Experimental product integration |

Provider keys should be supplied through environment variables or session-only settings. They must never be committed to the repository or included in exported companion data.

---

## Architecture

```text
                            ┌────────────────────────────┐
                            │   apps/desktop/src-tauri   │
                            │   transparent desktop UI   │
                            │   tray · hotkeys · windows │
                            └─────────────┬──────────────┘
                                          │ Tauri IPC
                            ┌─────────────▼──────────────┐
                            │   apps/desktop/frontend    │
                            │   React + Vite             │
                            │   overlay · controls       │
                            │   composer · dashboard     │
                            └────────┬──────────┬────────┘
                                     │ /ws      │ /api
                           ┌─────────▼──────────▼─────────┐
                           │      apps/backend            │
                           │ FastAPI + WebSocket          │
                           │ wiring.py assembles adapters │
                           └──────────────┬───────────────┘
                                          │ Protocols
   ┌──────────────┬──────────────┬────────┴────────┬──────────────┬──────────────┐
   │              │              │                 │              │              │
┌──▼─────┐  ┌─────▼──────┐  ┌────▼────────┐  ┌────▼────────┐ ┌───▼─────────┐ ┌──▼─────┐
│  LLM   │  │   Voice    │  │   Avatar    │  │    Tasks    │ │   Vision    │ │  Core  │
│OpenRtr │  │ STT + TTS  │  │Director +   │  │TaskRouter + │ │ detectors + │ │events +│
│Ollama  │  │Chatterbox  │  │renderers    │  │adapters     │ │classifiers  │ │schemas │
└────────┘  └────────────┘  └─────────────┘  └─────────────┘ └─────────────┘ └────────┘
```

### Runtime flow

```text
Text / PTT / wake input
          ↓
Runtime turn supervisor
          ↓
Conversation context + optional memory
          ↓
Task intent detection or LLM generation
          ↓
Structured response
          ↓
Text presentation + optional TTS
          ↓
Avatar emotion / action directive
          ↓
Optional memory write and diagnostics
```

The architecture follows five conceptual layers:

| Layer | Responsibility |
|---|---|
| Foundation | Contracts, schemas, configuration, events, lifecycle, and logging |
| Sensors | Text, microphone/STT, optional camera and contextual input |
| Cognition | LLM routing, prompts, structured responses, and optional memory retrieval |
| Effectors | Avatar behavior, speech output, and agentic task execution |
| Surfaces | FastAPI, WebSocket, React dashboard, and Tauri desktop windows |

---

## Wire protocol

Frontend and backend communicate through typed WebSocket messages.

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
{ "type": "ptt.down" }
{ "type": "ptt.up" }
{ "type": "mode.toggle", "key": "continuous_listening|live_wake|agent_voice", "value": true }
{ "type": "task.cancel", "handle": { "id": "...", "runtime": "..." } }
```

The normative protocol and adapter definitions live in [`docs/contracts.md`](docs/contracts.md).

---

## Repository layout

```text
openmimicry/
├── packages/
│   ├── openmimicry-core/       # Contracts, schemas, events, configuration, runtime
│   ├── openmimicry-llm/        # LLM adapters and routing
│   ├── openmimicry-voice/      # STT, TTS, workers, and speech control
│   ├── openmimicry-stt/        # Sensor-layer STT facade
│   ├── openmimicry-tts/        # Effector-layer TTS facade
│   ├── openmimicry-avatar/     # Avatar director, orchestrator, and renderers
│   ├── openmimicry-tasks/      # Task router and task-runtime adapters
│   ├── openmimicry-memory/     # Optional long-term memory
│   └── openmimicry-vision/     # Optional vision detectors and classifiers
├── apps/
│   ├── backend/                # FastAPI backend and adapter assembly
│   ├── desktop/
│   │   ├── frontend/           # React + Vite interface
│   │   └── src-tauri/          # Native Tauri 2 shell
│   ├── unity-bridge/           # Unity integration example
│   └── external-echo/          # Reference external-renderer server
├── characters/                 # Bundled character packs
├── config/profiles/            # Runtime profiles
├── docs/                       # Contracts, architecture, modules, security, and guides
├── scripts/                    # Validation, diagnostics, installation, and launch helpers
├── tests/                      # Unit, contract, integration, and security tests
├── docker/
├── docker-compose.yml
├── Makefile
└── scripts/win/                # Windows wrappers and launchers
```

---

## Extending OpenMimicry

Every major capability is a plug point.

| Plug point | Entry-point group | Example extension |
|---|---|---|
| LLM adapter | `openmimicry.contracts.llm` | Add another local or cloud model provider |
| STT adapter | `openmimicry.contracts.stt` | Whisper, Vosk, cloud STT, or custom sensor input |
| TTS adapter | `openmimicry.contracts.tts` | System voice, ElevenLabs, Azure, OpenAI, or another local engine |
| Avatar runtime | `openmimicry.contracts.avatar_runtime` | Live2D, pixel pet, Blender, or a custom renderer |
| Task runtime | `openmimicry.contracts.task_runtime` | OpenClaw, PicoClaw, workflow engine, or restricted local executor |
| Vision detector | `openmimicry.contracts.vision_detector` | Holistic, MoveNet, ONNX, or a custom detector |
| Vision classifier | Vision classifier entry-point groups | Rule-based, sklearn, ONNX, or another classifier |

New implementations should depend on contracts rather than importing concrete adapters from another package.

---

## Privacy and security posture

- **Local-first.** Ollama, local voice, and mocked profiles allow operation without a mandatory cloud provider.
- **Secrets stay outside the repository.** API keys should come from environment variables or session-only settings.
- **Voice cloning requires consent.** Voice references are treated as biometric material and should never be exported silently.
- **Vision remains opt-in.** Camera access must require explicit enablement and visible user control.
- **Text remains authoritative.** Optional audio, memory, vision, or task failures must not erase a valid text response.
- **Task execution is constrained.** Local execution should use explicit allowlists and centralized approval for side effects.
- **Imported archives are validated.** Character and companion ZIPs should enforce path, size, checksum, and duplicate protections.
- **Logs should be redacted.** Secrets, raw voice references, and unnecessary sensitive content must not appear in diagnostics.

See [`SECURITY.md`](SECURITY.md) and [`docs/licensing.md`](docs/licensing.md) for the full policies.

---

## Common development commands

```bash
make help                         # list available targets
make install PROFILE=basic        # install workspace and basic dependencies
make doctor                       # validate the development environment
make backend                      # run FastAPI on :8000
make frontend                     # run Vite on :5173
make desktop                      # launch the Tauri desktop application
make test                         # run Python and frontend tests
make ci                           # lint, type-check, import checks, and tests
make docker-up                    # start the backend through Docker Compose
make release-preview              # inspect the release plan without publishing
```

Windows equivalents live in [`scripts/win/`](scripts/win/).

---

## Documentation

- **Roadmap:** [`ROADMAP.md`](ROADMAP.md)
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)
- **Contracts:** [`docs/contracts.md`](docs/contracts.md)
- **Architecture:** [`docs/architecture.md`](docs/architecture.md) and [`docs/architecture/`](docs/architecture/)
- **Event flows:** [`docs/event_flows.md`](docs/event_flows.md)
- **Character packs:** [`docs/character_packs.md`](docs/character_packs.md)
- **Avatar modalities:** [`docs/avatar_modalities.md`](docs/avatar_modalities.md)
- **Desktop overlay:** [`docs/desktop_overlay.md`](docs/desktop_overlay.md)
- **Voice modes:** [`docs/voice_modes.md`](docs/voice_modes.md)
- **Memory:** [`docs/memory.md`](docs/memory.md)
- **Voice providers:** [`docs/voice_providers.md`](docs/voice_providers.md)
- **Task delegation:** [`docs/task_delegation.md`](docs/task_delegation.md)
- **External runtimes:** [`docs/external_runtimes.md`](docs/external_runtimes.md)
- **Configuration:** [`docs/configuration.md`](docs/configuration.md)
- **Testing and CI:** [`docs/testing_and_ci.md`](docs/testing_and_ci.md)
- **Migration:** [`docs/migration.md`](docs/migration.md)
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Security:** [`SECURITY.md`](SECURITY.md)

---

## Contributing

OpenMimicry is being developed in public and welcomes focused contributions.

Good first contribution areas include:

- Linux and macOS validation;
- ElevenLabs end-to-end testing;
- character-pack examples;
- diagnostics and fresh-clone tests;
- documentation corrections;
- accessibility checks;
- adapter conformance fixtures;
- optional renderer validation.

Before opening a pull request, read [`CONTRIBUTING.md`](CONTRIBUTING.md), keep changes inside the relevant contract boundary, and include tests or reproducible acceptance evidence whenever possible.

---

## Star history

<p align="center">
  <a href="https://www.star-history.com/?type=date&repos=Gabriel382%2FOpenMimicry">
    <picture>
      <source
        media="(prefers-color-scheme: dark)"
        srcset="PASTE_THE_GENERATED_DARK_IMAGE_URL_HERE"
      />
      <source
        media="(prefers-color-scheme: light)"
        srcset="PASTE_THE_GENERATED_LIGHT_IMAGE_URL_HERE"
      />
      <img
        alt="OpenMimicry star history"
        src="PASTE_THE_GENERATED_LIGHT_IMAGE_URL_HERE"
      />
    </picture>
  </a>
</p>

---

## License

OpenMimicry source code is released under the [MIT License](LICENSE).

Optional providers, transitive packages, imported character assets, voice models, and cloud services retain their own terms. Review [`docs/licensing.md`](docs/licensing.md) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) before commercial redistribution.

---

<div align="center">

**OpenMimicry v0.5.1 beta — a working 2D desktop companion today, a replaceable multimodal runtime for tomorrow.**

</div>
