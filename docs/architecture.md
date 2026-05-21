# OpenMimicry Architecture

Status: proposal, target v0.2.0
Audience: contributors, reviewers, recruiters reading the repo

This document is the entry point to OpenMimicry's design. It defines the repository layout, module boundaries, contracts between modules, and the overall philosophy. Deep dives live in the companion docs linked below.

OpenMimicry is **a modular avatar interface layer for LLMs, voice systems, and agentic task runtimes** — not a desktop chatbot with a 2D image attached. The same backend, LLM, voice, and task layer can drive a 360-pixel sprite, a Three.js VRM model, a procedural live-3D avatar, or a Unity scene over WebSocket.

## 1. Goals and non-goals

OpenMimicry is a local-first desktop companion framework. An animated 2D/3D avatar lives on the user's screen, listens, talks, and can delegate work to external agentic systems. The framework is modular enough that any one of those capabilities (LLM, TTS, STT, task runtime, **avatar runtime**, desktop shell) can be swapped without touching the others.

In scope:

- A small, typed Python core that owns state, events, and configuration.
- Clean adapter contracts for LLMs, speech-to-text, text-to-speech, external task runtimes, **and avatar runtimes**.
- A pluggable avatar layer: Sprite2D (default), Advanced 2D, lightweight 3D (Three.js / VRM / glTF), Live 3D, Unity (via protocol), and external renderers — all behind one `AvatarRuntimeAdapter` interface.
- A Tauri + React desktop shell with a transparent overlay and a separate panel window.
- YAML-driven configuration, validated by Pydantic.
- Reproducible installs, type-checked Python, linted code, tested adapters, and tagged releases.

Out of scope for v0.2.x:

- Hosted/multi-user deployments.
- Mobile clients.
- Training or fine-tuning models.
- Plugin marketplaces.

## 2. Architectural philosophy

Four rules drive every decision in the rest of this document.

**Hexagonal core.** Domain logic lives behind small interfaces. Concrete libraries (LiteLLM, RealtimeTTS, RealtimeSTT, mcp-agent, Tauri) sit on the outside and implement those interfaces. The avatar/runtime never imports a concrete library.

**Events, not RPC.** Modules talk to each other through a typed in-process event bus, not by reaching across module boundaries. The desktop UI subscribes to a stream of directives; it does not pull on the LLM.

**One source of truth per concern.** Configuration is loaded once into a validated `AppConfig`. Runtime state lives in `RuntimeStore`. Animation state lives in the avatar state machine. No module owns "a copy" of another's state.

**Honest seams.** Every adapter has an explicit contract, an example implementation, a mock, and a test. New adapters are added by satisfying the contract, not by editing the core.

## 3. Repository layout

```text
openmimicry/
  packages/                         # Pure Python, no UI
    openmimicry-core/               # Config, events, runtime, schemas
    openmimicry-avatar/             # Director + AvatarRuntimeAdapter contract + runtimes
      src/openmimicry/avatar/
        director.py                 # RuntimeEvent -> AvatarDirective
        orchestrator.py             # Director <-> chosen runtime
        runtimes/
          base.py                   # AvatarRuntimeAdapter Protocol
          sprite2d/                 # Sprite2DAvatarAdapter (default)
          advanced2d/               # Live2D / Spine / Rive / Lottie adapters
          threejs/                  # ThreeJSAvatarAdapter (+ VRM, glTF loaders)
          live3d/                   # Live3DAvatarAdapter (blending, gaze, mouth)
          unity/                    # UnityAvatarAdapter (WS/HTTP/TCP bridge)
          external/                 # ExternalAvatarAdapter (generic transport)
          mock/                     # MockAvatarAdapter (tests)
    openmimicry-voice/              # STT/TTS adapter contracts + RealtimeSTT/TTS impls
    openmimicry-llm/                # LLMAdapter contract + LiteLLM impl
    openmimicry-tasks/              # TaskRuntimeAdapter contract + adapters
  apps/
    backend/                        # FastAPI process: HTTP + WebSocket transport
    desktop/
      frontend/                     # React/Vite UI (overlay + panel routes)
        src/runtimes/
          sprite2d/                 # frame renderer
          threejs/                  # Three.js scene + VRM viewer
          live3d/                   # blending + mouth + gaze controllers
          unity_bridge/             # message-protocol bridge UI
      src-tauri/                    # Tauri shell (windows, tray, IPC)
    unity/                          # OPTIONAL: Unity sample project (not in Python install)
  characters/                       # Shipped character packs (octomimic, mimic_blue, ...)
  config/                           # Example YAML configs + JSON schemas
  docs/                             # This folder
  tests/
    unit/                           # Per-package unit tests
    integration/                    # Cross-package integration tests
    e2e/                            # Backend + frontend smoke tests
    contract/                       # Per-adapter contract suites (LLM, STT, TTS, Task, AvatarRuntime)
  scripts/                          # Dev helpers: doctor, pack validator, release
  .github/
    workflows/                      # CI, release, docs
  Makefile
  pyproject.toml                    # Workspace root, uv-managed
  README.md
  ROADMAP.md
  CHANGELOG.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  LICENSE
```

Notes on the layout:

- `packages/` uses a workspace (uv or hatch) so each package has its own `pyproject.toml`, version, and dependency set, but they install together from the root.
- `apps/backend/` is the only place that wires concrete adapters together. It is a thin process; all logic lives in `packages/`.
- `apps/desktop/` is split: the React app and the Rust/Tauri shell. They share no code with `packages/` other than over the wire.
- `characters/` and `config/` ship as data. Packs are self-contained folders with a manifest.
- Tests live at the repo root, not inside each package, so cross-package integration tests are first-class.

## 4. The six modules at a glance

| Module | Owns | Depends on | Never imports |
|---|---|---|---|
| `openmimicry-core` | `AppConfig`, `EventBus`, `RuntimeStore`, lifecycle, logging | Pydantic, stdlib | LiteLLM, RealtimeTTS, RealtimeSTT, mcp-agent, FastAPI, Tauri |
| `openmimicry-avatar` | `AvatarDirector`, `AvatarOrchestrator`, `AvatarRuntimeAdapter` + Sprite2D/Advanced2D/Three.js/Live3D/Unity/External runtimes, pack loader | core; rendering libs only inside the per-runtime modules | Anything voice/LLM/UI |
| `openmimicry-voice` | `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController` | core; RealtimeSTT/TTS only inside the `realtime_*` impl modules | LLM, tasks, UI |
| `openmimicry-llm` | `LLMAdapter`, `Router`, prompt registry | core; LiteLLM only inside `litellm_adapter` | Voice, avatar, UI |
| `openmimicry-tasks` | `TaskRuntimeAdapter`, task router | core; `mcp-agent` only inside `mcp_agent_adapter` | Voice, avatar, UI |
| `apps/backend` | HTTP + WebSocket transport, wiring | All packages | — |
| `apps/desktop` | Windows, rendering, input | Backend (over IPC/WS only) | Any Python package |

Detailed responsibilities and module-internal folder layouts live in the companion docs:

- [`adapters.md`](./adapters.md) — full LLM, STT, TTS, Task, and AvatarRuntime contracts.
- [`avatar_modalities.md`](./avatar_modalities.md) — the six rendering modalities, AvatarRuntimeAdapter, normalized directive schema, install profiles.
- [`event_flows.md`](./event_flows.md) — the four canonical flows (text, PTT, wake, task).
- [`voice_modes.md`](./voice_modes.md) — wake/PTT/agent-voice toggles and barge-in.
- [`task_delegation.md`](./task_delegation.md) — TaskRuntimeAdapter and the runtimes.
- [`character_packs.md`](./character_packs.md) — Sprite2D pack format, emotion + emotion_speaking variants.
- [`desktop_overlay.md`](./desktop_overlay.md) — transparent windows and click-through strategy.
- [`configuration.md`](./configuration.md) — YAML config layout and schemas.
- [`testing_and_ci.md`](./testing_and_ci.md) — Ruff, type-checking, pytest, GH Actions, releases.
- [`migration.md`](./migration.md) — phased plan from the current prototype.
- [`readme_guide.md`](./readme_guide.md) — how to write the public README.

## 5. Core contracts (one-line summary)

Detailed signatures in [`adapters.md`](./adapters.md). Each contract is a small Protocol or ABC, async by default.

```text
LLMAdapter             generate(prompt, *, stream, tools) -> AsyncIterator[LLMChunk]
STTAdapter             start(), stop(), transcripts: AsyncIterator[Transcript]
TTSAdapter             speak(text|stream, *, voice, on_chunk) -> Awaitable[None]; stop()
SpeechController       ptt_down(), ptt_up(), say(text), interrupt()
WakeController         enable(name), disable(); wake_events: AsyncIterator[WakeEvent]
TaskRuntimeAdapter     submit(task), status(id), cancel(id), updates(id): AsyncIterator[TaskUpdate]
AvatarRuntimeAdapter   load_character(id, cfg), apply_directive(d), set_text(s),
                       start_speaking(text?), stop_speaking(), set_visibility(b),
                       healthcheck(), shutdown()
AvatarDirector         on_event(RuntimeEvent) -> Optional[AvatarDirective]
AvatarOrchestrator     director + chosen AvatarRuntimeAdapter; swap_runtime()
```

## 6. Key data schemas

These live in `openmimicry-core/schemas/` so every other package can import them without circular dependencies. All are Pydantic v2 models, frozen by default.

- `AppConfig` — top-level validated config tree (LLM, voice, avatar, tasks, UI).
- `RuntimeEvent` — discriminated union: `UserTextSubmitted`, `UserSpeechStarted`, `UserSpeechFinal`, `LLMStarted`, `LLMTokenStreamed`, `LLMReplyComplete`, `TTSStarted`, `TTSChunkSpoken`, `TTSFinished`, `TTSInterrupted`, `WakeDetected`, `TaskSubmitted`, `TaskUpdated`, `TaskCompleted`, `ConfigUpdated`, `Error`.
- `AvatarDirective` — normalized, modality-independent: `{ state, emotion, animation?, speaking, text?, next_state?, duration_ms?, intensity?, gesture?, gaze?, metadata }`. Sprite2D consumes a subset; Live 3D and Unity consume the full shape. Full schema in [`avatar_modalities.md`](./avatar_modalities.md) §3.
- `State` — `idle | listening | thinking | speaking | happy | error` (the runtime state, extensible).
- `Emotion` — `neutral | happy | sad | angry | confused | focused | worried` (the affective dimension, extensible).
- `LLMChunk` — `{ delta: str, role: "assistant", finish_reason?, usage? }`.
- `Transcript` — `{ text: str, is_final: bool, confidence?, segments? }`.
- `TaskRequest`, `TaskUpdate`, `TaskResult` — for the task module.

Schema files are versioned. Breaking changes bump a `schema_version` field and the runtime refuses to load older configs without an explicit migration.

## 7. The event bus

A single in-process bus, `core.events.EventBus`, implemented as an `asyncio.Queue` per subscriber with a publish-fan-out producer. Two reasons it's worth doing in-process and not via Redis or similar:

- Everything runs in one backend process. Cross-process traffic only happens at the FastAPI/WebSocket boundary to the desktop.
- It keeps the test surface small: tests publish events and assert on what comes out.

The bus is the only path between modules. The desktop subscribes via WebSocket to a filtered projection (`AvatarDirective`, `TranscriptPreview`, `LLMTokenStreamed`, `SpeechBubbleText`, `Error`).

## 8. Configuration

YAML loaded at startup from `config/app.yaml`, layered with environment overrides (`OPENMIMICRY__LLM__MODEL=...`), validated into `AppConfig`. Hot reload is supported but limited to safe sections (UI text, avatar pack swap, prompt templates). Adapter swaps require a restart and the doctor command will say so.

Full schema in [`configuration.md`](./configuration.md). Worked example:

```yaml
schema_version: 1
app:
  log_level: INFO
  data_dir: ~/.openmimicry

llm:
  adapter: litellm
  model: openrouter/anthropic/claude-3.5-sonnet
  temperature: 0.7
  api_base: null
  fallback:
    adapter: litellm
    model: ollama/llama3.1

voice:
  stt:
    adapter: realtimestt
    language: en
    vad: silero
    wake:
      enabled: true
      names: ["Mimi", "Hey Mimi"]
  tts:
    adapter: realtimetts
    engine: coqui
    voice: en_female_1
    interruptible: true
  modes:
    text_always_on: true
    push_to_talk_hotkey: "Ctrl+Space"
    live_wake: true
    agent_voice: true

avatar:
  runtime: sprite2d
  pack: octomimic
  default_state: idle
  default_emotion: neutral
  transition_ms: 120

tasks:
  default_runtime: mcp_agent
  runtimes:
    mcp_agent:
      adapter: mcp_agent
      servers:
        - name: filesystem
          command: ["uvx", "mcp-server-filesystem", "~/projects"]
    claude_code:
      adapter: claude_code
      cli: claude
    local_shell:
      adapter: local_shell
      allowlist: ["ls", "rg", "cat"]

ui:
  overlay:
    width: 360
    height: 360
    click_through_default: true
    always_on_top: true
  panel:
    width: 480
    height: 720
```

## 9. Process and window topology

```text
+--------------------------+        WebSocket          +-----------------------------+
|  apps/backend (FastAPI)  |  <----------------------> |  apps/desktop (Tauri+React) |
|                          |       HTTP (control)      |                             |
|  EventBus                |                           |  Window: overlay (transparent, click-through default)
|  RuntimeStore            |                           |  Window: panel   (regular, interactive)
|  All adapters wired      |                           |  Tray icon                  |
+--------------------------+                           +-----------------------------+
        |                                                          |
        |                                                          |
        v                                                          v
   LLM (LiteLLM)                                          React app: avatar renderer,
   STT (RealtimeSTT)                                      speech bubble, text input,
   TTS (RealtimeTTS)                                      voice control buttons
   Task adapters (mcp-agent, Claude Code CLI, ...)
```

Why two windows: the overlay window stays transparent and click-through almost always; the panel is a normal, interactive window for typing, settings, and conversation history. That avoids the trap of per-pixel hit-testing on the overlay (see [`desktop_overlay.md`](./desktop_overlay.md)).

## 10. Event flows (summary)

Full sequence diagrams in [`event_flows.md`](./event_flows.md). One-liner versions:

- **Text input.** Frontend POSTs `/chat` -> `UserTextSubmitted` -> avatar goes `thinking` -> `LLMAdapter.generate` streams tokens -> per-chunk `LLMTokenStreamed` to bus -> `TTSAdapter.speak` consumes the stream if agent voice is on -> avatar transitions `thinking -> speaking -> idle`.
- **Push-to-talk.** Hotkey down -> `SpeechController.ptt_down()` opens STT mic and stops any running TTS -> avatar `listening` -> hotkey up -> STT finalizes -> `UserSpeechFinal` -> same path as text.
- **Wake-name live mode.** `WakeController` runs the STT in wake-listening mode -> on wake event, full STT transcription starts -> partial transcripts publish `TranscriptPreview` for the speech bubble -> on final transcript, same path as text. Barge-in: if `TTSStarted` is active when speech is detected, `SpeechController.interrupt()` stops TTS and the avatar switches to `listening`.
- **Task delegation.** LLM tool-calls or intent classifier produces a `TaskRequest` -> `TaskRouter` picks an adapter -> `TaskRuntimeAdapter.submit` returns an id and an `updates` stream -> updates publish to the bus, the avatar shows `thinking_speaking` (or a dedicated `working` emotion if defined), and the frontend renders a task card.

## 11. Avatar directives

The avatar is pluggable. The runtime never tells a renderer "play file X" — it publishes a normalized `AvatarDirective`, and the chosen `AvatarRuntimeAdapter` translates that for its modality (sprite folder for Sprite2D, animation clip for Three.js, Animator parameter for Unity, and so on). The avatar director (in `openmimicry-avatar`) translates `RuntimeEvent` into `AvatarDirective`:

| Trigger event | Resulting directive |
|---|---|
| `UserSpeechStarted` | `state=listening, speaking=false` |
| `LLMStarted` (no tokens yet) | `state=thinking, speaking=false` |
| `LLMTokenStreamed` first chunk + `TTSStarted` | `state=speaking, speaking=true` |
| `TTSChunkSpoken` boundary | `speaking=true` heartbeat |
| `TTSFinished` or `TTSInterrupted` | `state=idle, speaking=false` |
| `Error` | `state=error, speaking=false` |
| `TaskCompleted` (success) | `state=happy, next_state=idle, duration_ms=cfg.celebration_ms` |
| Task running and no TTS active | `state=thinking, speaking=false` |

The full directive schema, modality-by-modality field mapping, and the `AvatarRuntimeAdapter` contract live in [`avatar_modalities.md`](./avatar_modalities.md). The Sprite2D pack format (`emotion + emotion_speaking` folder convention) is documented in [`character_packs.md`](./character_packs.md).

## 12. Interruptible TTS and barge-in

Detail in [`voice_modes.md`](./voice_modes.md). The short version:

- `TTSAdapter` exposes a cooperative `stop()` that cancels both playback and the underlying generator.
- `SpeechController` owns a single active TTS task. New `say(...)` calls first `await self._current.stop()`.
- The STT runs with VAD even while TTS is playing. When voice activity is detected and `voice.tts.interruptible` is true, the controller stops TTS and transitions the avatar to `listening`. This is the "barge-in" path.
- Audio loopback into the mic is mitigated by either (a) using a directional/USB mic, or (b) enabling RealtimeSTT's echo handling. We document both in the README under "Known issues" rather than silently doing the wrong thing.

## 13. Transparent overlay and click-through

Detail in [`desktop_overlay.md`](./desktop_overlay.md). The strategy is deliberately simple:

- Two windows. The overlay window is decoration-less, transparent, always-on-top, click-through by default. The panel window is normal.
- Click-through is toggled at the OS level via Tauri (`setIgnoreCursorEvents(true|false)`), not by reading pixel alpha. A configurable hotkey and a tray menu item flip it. While "interact mode" is on, the entire overlay is clickable; while off, all clicks fall through.
- Visual interaction with the avatar (drag to reposition, right-click for menu) is opt-in via a small interactive zone — a normal HTML element inside the overlay that grabs focus only when interact mode is on.
- We never attempt per-pixel hit testing. It is platform-fragile, expensive, and unnecessary for a companion overlay.

## 14. Configuration, observability, and lifecycle

- Single `AppConfig` validated at startup; reload reuses the same validator.
- Structured JSON logs via `structlog`, with a log subscriber on the event bus that records every `RuntimeEvent` at DEBUG and notable ones at INFO.
- `make doctor` checks Python, Node, Rust, Tauri, ffmpeg, ollama, and config validity.
- A `/health` endpoint reports adapter status and last error per adapter.

## 15. Testing

Detail in [`testing_and_ci.md`](./testing_and_ci.md). Three layers:

- **Unit** per package: `tests/unit/<package>/`. Pure functions, schema validation, state-machine transitions, adapter mocks.
- **Integration**: `tests/integration/`. Wire the EventBus + mock adapters and assert event flows end-to-end (e.g., a text input triggers the expected sequence of `RuntimeEvent`s and `AvatarDirective`s).
- **End-to-end smoke**: `tests/e2e/`. FastAPI test client + a real `MockLLMAdapter`, `MockTTSAdapter`, `MockSTTAdapter` to confirm the WebSocket projection looks right to a frontend. Optional Playwright pass against the Vite dev server for the panel route.

CI runs unit + integration on every PR; e2e on `main` and tags.

## 16. CI/CD

- **Lint and format**: Ruff (`ruff check`, `ruff format --check`).
- **Type-check**: `pyright` (strict on `openmimicry-core`, gradual elsewhere).
- **Test**: `pytest -n auto --cov`.
- **Frontend**: `npm run lint`, `npm run typecheck`, `npm test`.
- **Build matrix**: Ubuntu and Windows; Python 3.11 and 3.12.
- **Release**: tag `vX.Y.Z` triggers a release workflow that builds Python wheels, Tauri bundles for Windows and Linux, generates a changelog from Conventional Commits, and publishes a GitHub Release.
- **Versioning**: SemVer. `0.x` while contracts move; `1.0` only after the adapter contracts are frozen.

## 17. Documentation

Each public adapter contract has a one-page doc with: contract signature, lifecycle, error model, an "implement your own" walkthrough, and at least one reference implementation. The README ([`readme_guide.md`](./readme_guide.md)) is built to make the project legible in 60 seconds: what it is, what works today, what's planned, a 30-second install, a screenshot, and links to the architecture.

## 18. Migration plan

The full phased plan is in [`migration.md`](./migration.md). It is deliberately incremental: the current prototype stays runnable on `main` throughout. Packages are introduced side-by-side under `packages/`, code is moved in module by module, and the legacy `core/`, `backend/`, `tts/`, `avatar/`, `backends/` folders are deleted only when the new home reaches parity.

Headline phases:

```text
P0  Tooling baseline           Ruff, pyright, pytest, CI skeleton, Conventional Commits
P1  Core extraction            openmimicry-core (config, events, schemas, runtime)
P2  LLM adapter                openmimicry-llm with LiteLLM behind LLMAdapter
P3  Voice adapters             openmimicry-voice with RealtimeSTT/RealtimeTTS impls
P4  Avatar baseline            openmimicry-avatar + AvatarRuntimeAdapter + Sprite2D runtime
P5  Task delegation            openmimicry-tasks + mcp-agent + Claude Code adapter
P6  Backend rewire             apps/backend uses only packages/*
P7  Desktop polish             Overlay/panel split, click-through toggle, tray
P8  Release v0.2.0             Tagged release, signed bundles, README screenshot
P9  Modality: Three.js + VRM   Lightweight 3D runtime in the overlay window
P10 Modality: Live 3D          Blending, mouth from TTS, gaze, gesture
P11 Modality: Unity bridge     Protocol + sample Unity project under apps/unity/
P12 Modality: External         Generic transport adapter + docs for third parties
```

Each phase has its own milestone, its own issues, and a "done when" checklist in [`migration.md`](./migration.md).
