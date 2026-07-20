# Changelog

All notable changes to OpenMimicry are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added explicit, persisted OpenRouter internet grounding in the dashboard.
  It uses OpenRouter's documented online model variant, remains off by default,
  and surfaces the provider's linked citations in normal assistant replies.

- Added named Voice Profiles stored outside the repository, with Chatterbox
  WAV/MP3 references, ElevenLabs voice IDs, consent metadata, selection,
  activation, bounded import, and optional-reference export.
- Added whole Companion Profile import/export for the current character images,
  personality, appearance, and selected named voice. Secrets, memory records,
  history, logs, and model caches are excluded, while biometric audio requires
  explicit confirmation in both directions.
- Added dashboard controls to create, choose, import, export, and activate
  voices and complete companions.
- Added a runtime supervisor with process identity, lifecycle snapshots,
  component health projection, and `/health/live`, `/health/ready`, and
  `/health/components` endpoints.
- Added correlated `turn.state`, `runtime.state`, and `component.health`
  events/messages with replay for newly opened desktop windows.

### Changed

- Conversation submission is strict single-flight: overlapping text, PTT,
  continuous, or wake turns are rejected immediately instead of being hidden
  in an internal queue.
- Desktop text and PTT controls now follow backend readiness and the active turn
  lease while lock, drag, settings, and exit controls remain available.
- Dashboard personality edits now persist to the user's OpenMimicry data
  directory and overlay the tracked default instead of modifying a repository
  file.

### Fixed

- Automatic Faster-Whisper device selection now proves the CUDA 12 cuBLAS and
  cuDNN speech DLLs on Windows before opening the microphone. An incompatible
  CUDA 11/PyTorch environment selects the stable CPU/INT8 lane immediately
  instead of failing on the first utterance and retrying noisily.
- Thinking, listening, transcription, refresh, and backend-availability states
  now use a white status balloon above the avatar. The red toolbar banner is
  reserved exclusively for actionable errors.
- The last successfully loaded character pack is persisted, private pack paths
  are resolved before orchestrator startup, and the active named voice is
  recovered from the persisted TTS profile. Personality remains in the private
  persistent personality overlay.
- Companion export accepts human-friendly IDs such as `GLaDOS-v1`, normalizes
  them to safe portable IDs, downloads through a checked blob response, and
  reports failures inline instead of navigating to a 422 response.
- Desktop appearance loading waits for the direct backend WebSocket to connect,
  eliminating repeated Vite `/appearance` proxy errors during backend startup
  or refresh. The dashboard embeds its favicon and no longer requests a missing
  `/favicon.ico`.
- LiteLLM's generic feedback footer is suppressed while the concrete classified
  provider exception and traceback are retained in OpenMimicry diagnostics.

- User-created and imported character packs now install under the private
  OpenMimicry data directory; bundled character roots remain discoverable and
  read-only, with a validated asset route serving both locations.
- Windows installation paths are resolved from the OpenMimicry script location,
  so invoking an installer from another repository cannot silently select that
  repository's `.venv`.
- Installers claim and validate environment ownership before changing packages;
  an existing non-empty, unclaimed environment is rejected with an actionable
  recovery message.
- Chatterbox installation now checks and repairs Perth after a Torch/Torchvision
  import repair instead of skipping it and reporting a false CUDA mismatch.
- Runtime verification reports the exact failing Torch, Torchaudio, Torchvision,
  Chatterbox, Perth, CUDA, or device condition instead of a generic PyTorch error.
- A late TTS finish/interruption from an older utterance can no longer replace
  the listening or thinking animation for the current input.
- Accepted PTT/wake input now transitions through the same authoritative
  thinking state as typed input; rejected ambient wake transcripts remain in
  listening state.
- New character packs and other local companion assets are ignored by default;
  only `mimic_blue`, `octomimic`, and `octomimic_vrm` remain source-controlled.

## [1.6.4] — Chatterbox Perth startup repair

### Fixed

- Detect the defective `resemble-perth` state where the package imports but
  `PerthImplicitWatermarker` is `None`; this state can no longer produce a
  misleading successful runtime report.
- Repair only Perth from the official MIT upstream repository at immutable
  commit `ce86c49d029f42272c1902eccb675556b9ed2330`, while preserving the
  verified Torch, Torchaudio, Torchvision, CUDA, and NumPy installation.
- Resolve the real Perth constructor before Chatterbox model construction and
  surface the underlying import failure instead of Chatterbox's unhelpful
  `'NoneType' object is not callable` exception.
- Keep Chatterbox's audio watermark active. OpenMimicry never substitutes the
  Perth dummy/no-watermark implementation.

### Diagnostics

- Runtime reports now include Perth's installed version, package origin, and
  `perth_watermarker_callable` result. The v1.6.4 preflight marker is written
  only after the real Chatterbox Turbo model loads successfully.

## [1.6.3] — unified and non-destructive Chatterbox setup

### Fixed

- Accepted CUDA build suffixes such as `torchvision 0.21.0+cu126` when
  verifying the PyTorch 2.6 version triplet.
- Preserved a complete CUDA runtime that already imports, sees the GPU, and
  matches Chatterbox instead of guessing CUDA 11.8 when `nvidia-smi` omits its
  banner version and downloading a multi-gigabyte downgrade.
- Limited Torch repairs to Torch, Torchvision, and Torchaudio with `--no-deps`
  so an accelerator repair cannot unnecessarily reinstall NumPy and unrelated
  application dependencies.

### Changed

- Folded Chatterbox detection, installation repair, verification, model
  prewarming, profile selection, and startup into the existing Windows
  `start-openrouter-voice.ps1` flow.
- Removed the separate Chatterbox PowerShell and shell launchers. Installation
  remains an ordinary `openrouter-chatterbox` profile; execution uses the same
  voice/backend entry points as the other providers.

## [1.6.2] — reliable Chatterbox installation and NumPy 2 compatibility

### Fixed

- Kept Chatterbox 0.1.7 reference conditioning in float32 inside its isolated
  worker, fixing `expected scalar type Double but found Float` with NumPy 2.x
  without modifying files under `.venv`.
- Added hardware-aware installation of the official, version-matched PyTorch
  2.6 CUDA wheels when an NVIDIA GPU is present; macOS retains its MPS-capable
  platform wheel and CPU remains a deliberate fallback.
- Added dedicated Windows and Unix Chatterbox launchers with dependency
  repair, CUDA verification, bounded one-time model prewarming, the correct
  profile, and a 180-second cold-start deadline.
- Persisted the Chatterbox readiness deadline alongside dashboard provider
  selection so a former Piper configuration cannot retain a 30-second limit.
- Prevented two-second HTTP health checks from cold-starting or orphaning a
  multi-gigabyte Chatterbox worker after cancellation.

### Diagnostics

- Worker handshakes now report device, Torch/CUDA, NumPy, and compatibility
  status, while startup and synthesis failures include stable error codes and
  retain their child-process tracebacks in diagnostics.

### Tests

- Added regressions for NumPy 2 float promotion, hardware channel selection,
  unsupported Blackwell/Torch combinations, non-starting health checks,
  dashboard timeout persistence, and the dedicated Windows launcher.

## [1.6.1] — memory settings validation hotfix

### Fixed

- Prevented the dashboard from submitting the invalid combination of enabled
  long-term memory with the `none` provider. Enabling memory now defaults to
  private Local SQLite storage, while choosing `None` turns memory off.
- Converted nested memory-configuration validation failures into safe HTTP 422
  responses instead of uncaught HTTP 500 errors and server tracebacks.
- Added an explicit endpoint check for enabled Hindsight memory and readable
  dashboard error messages for rejected settings.
- Included `openmimicry-memory` in Pyright source resolution while retaining a
  narrow ignore for its intentionally optional Hindsight client import.

### Tests

- Added regression coverage for `enabled + none`, Hindsight without an
  endpoint, non-persistence of invalid settings, and dashboard normalization.

## [1.6.0] — configurable interaction, optional memory, and voice providers

### Added

- Four utterance-correlated reply-presentation modes with a character-based
  reading timer and speech-terminal hold.
- Named OpenRouter/Ollama backends, bounded catalog discovery, model roles,
  session-only tokens, and editable personality.
- Disabled-by-default SQLite/Hindsight memory with deterministic or independent
  LLM extraction, deadlines, retention, local CRUD, and export.
- Hardened character ZIP import, simple Sprite2D authoring, and a versioned
  template archive.
- OS-native TTS, free local consent-gated Chatterbox cloning, ElevenLabs BYOK,
  schema v2 migration, dependency profiles, and license audit tooling.

### Changed

- Default OpenRouter model is `openrouter/openai/gpt-oss-20b`.
- Commercial installs exclude Piper/Chatterbox and use host-native TTS; Piper
  remains an explicit community profile.
- Assistant bubbles dismiss only after the reading deadline and matching audio
  terminal event.

### Security

- Added session/environment-only provider secrets, loopback-only Ollama
  discovery, bounded provider responses, atomic prompt/settings writes,
  consented private voice-reference storage, and license-aware atomic pack
  installation.
- Memory cannot store raw audio and optional-subsystem failures cannot suppress
  typed chat.

## [1.5.1] — verified CUDA auto-selection fallback

### Fixed

- Treated CTranslate2 GPU enumeration as a hint instead of proof that the CUDA
  runtime is usable. `device: auto` now retries `medium.en` on CPU/INT8 when
  CUDA model loading or first inference fails, including a missing
  `cublas64_12.dll`.
- Reported the hardware and compute type that actually passed the voice
  preflight, together with the CUDA fallback reason.
- Kept `device: cuda` strict so an explicitly requested GPU configuration still
  fails with the original actionable dependency error.

### Added

- Regression coverage for CUDA model-load failure, lazy CUDA inference failure,
  and strict explicit-CUDA behavior.

## [1.5.0] — isolated, repeatable Windows voice runtime

### Changed

- Replaced RealtimeSTT/RealtimeTTS as the Windows default with a preloaded,
  supervised Faster-Whisper input process and disposable Piper output jobs.
- Raised the CPU recognition default from `small.en` to `medium.en`; added
  `distil-large-v3` and `large-v3` dashboard selections.
- Published assistant text and history before queuing audio, so TTS failure can
  no longer hide an OpenRouter response or block another conversation turn.
- Started the speaking animation only after the playback process reports that
  audio actually began. Stale synthesis events cannot replace listening.

### Added

- `scripts/voice_doctor.py`, exercised automatically by the Windows launcher,
  validates audio devices, several sequential Piper jobs, WAV integrity, and
  a real Faster-Whisper transcription before voice is enabled.
- Process-boundary regressions for two STT turns, two TTS turns, and recovery
  after forcibly terminating a hung playback job.

### Deprecated

- `realtimestt` and `realtimetts` remain available through the
  `legacy-realtime` extra but are no longer used by the supported Windows
  profile.

## [1.4.2] — non-blocking audio stop and live-final priority

### Fixed

- Moved RealtimeTTS `stream.stop()` off the asyncio event loop and bounded the
  wait, preventing Windows/SystemEngine shutdown from freezing PTT, WebSockets,
  typed chat, and passive-listener recovery after the first spoken answer.
- Replaced a wedged TTS worker with a fresh daemon COM lane, so the next answer
  can speak even when the previous third-party playback worker never exits.
- Bounded `SpeechController.interrupt()` so hold-to-talk opens promptly while
  slow audio cleanup finishes independently.
- Coalesced obsolete realtime STT previews and prioritized final transcripts,
  preventing live-wake commands from sitting behind an unbounded partial-text
  backlog until the mode was disabled.

### Added

- Lifecycle logs showing passive-listener consumption, final dequeue, bounded
  stop failures, and TTS worker-lane replacement.
- Regressions for a permanently blocking RealtimeTTS stop, recovery of the
  second spoken answer, PTT responsiveness during stuck cleanup, and a 500-item
  realtime-preview flood ahead of a final wake transcript.

## [1.4.1] — repeat-turn voice lifecycle recovery

### Fixed

- Drained cancelled RealtimeTTS executor work before accepting the next reply,
  preventing an interrupted first playback from permanently occupying the
  single Windows COM worker and silencing every later answer.
- Added per-reply readiness ownership and a bounded playback watchdog so stale
  TTS readiness cannot leak into the next turn and a broken audio stream
  restores passive voice input instead of freezing it indefinitely.
- Kept the prewarmed RealtimeSTT recorder reusable across ordinary pauses,
  removed non-operational wake metadata from its rebuild signature, and made
  stop sentinels synchronous on the owning event loop so they cannot terminate
  the next listening session.
- Decoupled accepted UI input from LLM/TTS completion while retaining ordered
  conversation execution, so a stuck audio operation cannot block later typed
  messages from appearing or prevent the WebSocket receive loop from running.
- Serialized all outbound writes per WebSocket and treated status/replay sends
  racing with a client close as clean disconnects instead of ASGI exceptions.

### Added

- Numbered conversation, STT-session, TTS-playback, and WebSocket lifecycle
  logging to a rotating per-process file under `~/.openmimicry/logs`.
- A dashboard **Download bundle** action and Windows fallback collector that
  package logs, relevant dependency versions, and sanitized runtime settings
  without reading `.env` or including API-key values.
- Repeat-turn regressions for cancelled/sequential TTS, recorder pause/restart,
  stale STT sentinels, closed-socket status sends, serialized socket writes,
  and non-blocking background conversations.

## [1.4.0] — ordered multimodal conversations and configurable local AI

### Fixed

- Serialized accepted text/PTT/wake turns so an older LLM response cannot
  arrive after a newer question and appear to answer the wrong prompt.
- Reused a prewarmed RealtimeTTS engine on one dedicated worker, fixing the
  Windows failure where only the first assistant reply produced audio.
- Preloaded RealtimeSTT at startup and finalized PTT on release, removing the
  first-press model load and making the hold/release boundary deterministic.
- Suppressed repeated wake finals inside a 2.5-second window while preserving
  every heard transcript in the dashboard for diagnosis.
- Delayed reply display until TTS reports playback start (with an explicit
  text fallback if audio cannot start), aligning visible and audible output.

### Added

- Four-pair successful conversation memory; ignored wake audio and failed
  turns are displayed but never added to future LLM context.
- Accurate `small.en` speech recognition by default, selectable
  `tiny.en`/`base.en`/`small.en` quality, wake-name transcription prompts,
  and editable aliases such as `Me me` for `Mimi`.
- Dashboard-visible model identity and live switching between configured
  OpenRouter and Ollama backends. The voice profile includes
  `ollama_chat/gpt-oss:20b` as its local option.
- Validated character-pack ZIP import with traversal, symlink, file-count,
  compressed-size, and expanded-size protections.
- Regression coverage for ordering, memory, wake rejection/deduplication,
  TTS engine reuse, STT model selection, backend switching, and ZIP import.

## [1.3.2] — reliable multi-turn voice and desktop event lifecycle

### Fixed

- Replaced RealtimeTTS's racy `play_async()`/`is_playing()` completion poll
  with blocking playback on a worker thread, so every reply waits for actual
  audio completion and subsequent replies speak reliably.
- Isolated stale React StrictMode WebSockets by connection generation and
  connected desktop windows directly to the backend, preventing duplicated
  bubble deltas and Vite `ws proxy socket error: ECONNABORTED` noise.
- Published each already-complete structured LLM reply as one display update
  while TTS starts, so text and voice become available together without
  artificial append-only chunks.
- Explicitly closed the three Tauri webview windows before process exit to
  reduce WebView2 `Chrome_WidgetWin_0` class-unregistration errors on Windows.

### Added

- Configurable `voice.stt.post_speech_silence_duration` endpointing (default
  `1.0`, range `0.2`–`3.0` seconds), passed through to RealtimeSTT and editable
  from the local dashboard without a restart.
- A toolbar reply-interaction toggle that temporarily changes the avatar from
  click-through to interactive, plus auto-following and keyboard-focusable
  speech-bubble scrolling.
- Regression coverage for repeat TTS playback, speech-pause propagation and
  persistence, passive-listener restart, and stale StrictMode sockets.

## [1.3.1] — voice turn completion and observable transcription

### Fixed

- Prevented passive RealtimeSTT from transcribing system TTS by pausing
  listening during playback in the safe default configuration and restoring it
  afterward.
- Contained intentional `asyncio.CancelledError` from interrupted TTS so every
  chat turn still emits its final reply and avatar cue instead of disconnecting
  the originating WebSocket and leaving the avatar in `speaking`.
- Reset incomplete bubble text at the start of every LLM turn, eliminating
  concatenated replies after an interrupted turn.
- Added an actionable Windows launcher error when another process already owns
  port 8000.

### Added

- Explicit PTT `listening` and `transcribing` stages plus recognized/no-speech
  results in both the toolbar and browser dashboard.
- Replayable in-memory conversation history for the latest 100 typed, voice,
  and assistant turns in the dashboard.
- `voice.modes.barge_in_enabled`, disabled by default for ordinary speaker and
  laptop-microphone setups; PTT interruption remains available at all times.

## [1.3.0] — stable Windows voice and name-gated companion controls

### Added

- Configurable wake-name listening: the hands-free mode accepts only final
  utterances beginning with the configured name (default `Mimi`) and strips
  that prefix before submitting the command.
- Local-dashboard wake-name editor backed by an ignored `config/user.yaml`
  overlay, with environment variables retaining highest precedence.
- A dedicated below-avatar message composer while drag, lock, PTT, wake
  listening, agent voice, settings, and exit stay in the top toolbar.
- A perceptible thinking-animation interval for both typed and spoken turns.

### Fixed

- Disabled Uvicorn reload in the Windows voice launcher so first-run
  `comtypes` file generation cannot restart FastAPI during TTS and disconnect
  every desktop WebSocket.
- Treated Starlette's shutdown-time disconnected-socket `RuntimeError` as a
  normal WebSocket close.
- Increased the PTT final-transcript allowance for Windows CPU/first-run
  Whisper latency.
- Preserved text input independently of agent-voice state and kept
  dashboard adapter diagnostics intact after saving a wake name.

### Changed

- The companion is implemented as three docked native windows: click-through
  avatar, interactive top toolbar, and interactive bottom composer.
- RealtimeSTT performs dictation; provider-independent wake-prefix matching is
  owned by `SpeechController`, allowing arbitrary user-selected names.

## [1.2.2] — Windows Python 3.13 voice compatibility hotfix

### Fixed

- Replaced the launcher's multiline `python -c` preflight with a checked-in
  Python script so Windows PowerShell cannot strip quotes from the command.
- Added `audioop-lts` automatically on Python 3.13 and newer, restoring the
  `RealtimeTTS` → `pydub` import path after Python removed the standard
  `audioop` module.
- Kept full stderr capture and automatic `.venv` repair while making the same
  file-based import check run both before and after installation.

## [1.2.1] — Windows voice preflight hotfix

### Fixed

- Prevented Windows PowerShell's `ErrorActionPreference=Stop` from terminating
  the launcher when Python writes an import traceback to stderr.
- Captured and displayed complete RealtimeSTT/RealtimeTTS diagnostics after a
  failed repair instead of reporting only `NativeCommandError`.
- Installed the upstream-recommended `faster-whisper` STT extra and `system`
  TTS engine extra for the `openrouter-voice` profile.
- Verified the concrete `AudioToTextRecorder`, `TextToAudioStream`, and
  `SystemEngine` imports before starting the backend.
- Selected CPU/int8 as the portable RealtimeSTT default instead of inheriting
  upstream's CUDA default on Windows machines without a CUDA runtime.

## [1.2.0] — avatar toolbar and continuous voice

### Added

- Top-docked avatar toolbar with drag, persistent lock, hold-to-talk, Auto
  listen, agent voice, browser-dashboard, exit, and text controls.
- VAD-driven `continuous_listening` mode with no wake phrase.
- FastAPI `/dashboard` for chat, settings, diagnostics, and replayed task cards.
- Windows voice-launcher preflight that repairs missing RealtimeSTT/RealtimeTTS
  in the backend's actual project virtual environment.

### Changed

- Removed the native startup panel; gear, tray, and `Ctrl+Shift+O` open the
  local browser dashboard.
- Docked the interactive toolbar above the transparent avatar.
- Global PTT now targets the toolbar and temporarily pauses/restores continuous
  listening so a single STT stream never has competing consumers.
- Voice status distinguishes selected adapters from importable audio backends
  and no longer labels mock adapters as real microphone/audio devices.

### Versioning

- Workspace applications and packages moved from `1.1.0` to `1.2.0`.

## [1.1.0] — desktop companion stabilization

### Added

- Separate always-on-top `avatar-controls` window with a drag handle and compact
  message field below the transparent avatar.
- Validated `config/theme.yml` appearance pipeline and public `GET /appearance`.
- Reading-time speech bubbles with configurable pad, per-character duration,
  cap, scrolling, and late-window replay.
- Allow-listed structured LLM reply envelope and additive `AvatarCue` event.
- Safe default/basic configuration and an `openrouter-voice` profile using
  local RealtimeSTT plus operating-system TTS.
- Windows `.env` launcher for the OpenRouter/voice profile.
- Voice adapter/status reporting and Tauri push-to-talk forwarding.

### Fixed

- Persisted drag movement, initial avatar replay, and always-on-top enforcement.
- Agent voice now gates later TTS; live-wake/PTT finals now enter chat.
- Runtime factories are registered and pack swap follows the current runtime.
- Task cancellation reaches the task router; the empty task UI explains its
  on-demand behavior.
- Happy structured cues use the bundled distinct happy Sprite2D frames.

### Versioning

- Workspace applications and packages moved from `1.0.0` to `1.1.0`.

## [1.0.0] — first stable release

The contract surface in [`docs/contracts.md`](docs/contracts.md) is frozen.
Within 1.x, every Protocol, schema, event variant, and §9 wire-protocol message
stays stable; additive amendments may land in minor releases. A `schema_version`
bump is reserved for the 2.0 line.

### Highlights at v1.0

- **6 publishable Python packages** behind one Protocol surface: `openmimicry-core`
  (frozen contracts + EventBus + Runtime + AppConfig), `-llm`, `-voice`, `-avatar`
  (with five concrete modalities), `-tasks`, `-vision` (optional, off by default).
- **3 apps**: FastAPI backend (M6, single concrete-adapter assembly point in
  `wiring.py`), React + Vite frontend with `/overlay` and `/panel` routes (M7),
  Tauri 2 desktop shell with two windows + tray + global hotkeys (M8).
- **5 avatar modalities** all behind the same `AvatarRuntimeAdapter` Protocol:
  Sprite2D (M4), Three.js with VRM/glTF (M9), Live3D drivers over Three.js
  (M10), Unity bridge with sample Unity project (M11), generic External
  WebSocket bridge with reference echo server (M12). Live runtime swap is
  preserved by `AvatarOrchestrator.swap_runtime`.
- **3 task runtimes** behind `TaskRouter` (M5): allowlist-only LocalShell,
  ClaudeCode CLI, MCP agent — plus a scripted mock that drives every
  integration test.
- **Vision** (M13) — optional MediaPipe Hands / Pose / Face → rule-based +
  sklearn/ONNX gesture/movement classifiers → `AvatarDirective` overrides.
  Off by default, consent-gated, frames never leave the process.
- **Docker** — `docker-compose.yml` + `docker/Dockerfile.{backend,frontend-dev}`.
  Single command brings up a mocks-only backend with `/health` wired.
- **Cross-platform**. `make` for Linux / macOS / WSL; `scripts/win/*.bat`
  wrappers for native Windows. Cross-platform `scripts/doctor.py` confirms
  the toolchain.
- **Tests at every layer** — ~250 Python unit + contract + integration tests,
  Vitest frontend tests, Rust shell tests. CI runs the full suite on every PR.

### Removed in 1.0

- The pre-restructure prototype directories (`avatar/`, `backend/`, `backends/`,
  `core/`, `frontend/`, `src-tauri/`, `tts/`, `packs/`, `profiles/`). Everything
  migrated into `packages/` and `apps/` during M0–M13. Run
  `bash scripts/cleanup-legacy.sh --apply` (or
  `scripts\win\cleanup-legacy.bat` on Windows) to purge them from an old clone.
- Root-level milestone notes (`Milestone.md`, `MILESTONE5_INTEGRATION.md`,
  `PATCH_NOTES.md`, `README_MILESTONE*.md`,
  `README_EMOTION_SPEAKING_PATCH.md`) — superseded by `docs/modules/M*.md`
  and the CHANGELOG entries below.

### Versioning

Every workspace package + app + Tauri shell is pinned to `1.0.0`. Cross-package
`openmimicry-core>=` lower bounds also bumped to `1.0.0`.

### Added (during the 1.0 cycle, oldest → newest)

- **M13 (`openmimicry-vision`):** the fifth sibling package — optional, opt-in webcam → hand / body / head detection + gesture and movement classification. **Off by default**; even with `vision.enabled: true`, no camera opens until the bus sees `ConsentResolved`. **Contracts amendment (additive, Stable, no `schema_version` bump)**: `packages/openmimicry-core/src/openmimicry/core/schemas/vision.py` introduces `Landmark` (3D + visibility/presence), `HandPose` (21 pts), `BodyPose` (33 pts), `HeadPose` (6-DoF + sparse landmarks), top-level `VisionFrame`, `GestureDetection`, `MovementDetection`, and `VisionConfig` (per-detector and per-classifier sub-blocks, `gesture_map` / `movement_map`); `openmimicry.core.contracts.vision` adds `VisionAdapter`, `LandmarkDetector` + specialisations (`HandDetector`, `BodyDetector`, `HeadDetector`), `GestureClassifier`, `MovementClassifier`; five new `RuntimeEvent` variants (`HandPoseStarted`, `HandPoseEnded`, `GestureDetected`, `MovementDetected`, `ConsentRequired`, `ConsentResolved`); `AppConfig.vision: VisionConfig | None`. **Package** `packages/openmimicry-vision/`: `mocks.py` (importable without OpenCV/MediaPipe — `MockVisionAdapter`, `MockHandDetector`, `MockGestureClassifier`, `MockMovementClassifier`); `pipeline/{capture,throttle}.py` (OpenCV-backed `VideoCapture` in a worker thread with drop-oldest queue; `Throttle` + `Debouncer` with pluggable clocks); `pipeline/detectors/{hands,body,head}.py` (MediaPipe Hands / Pose / Face wrappers, all lazy-imported, exposing the duck-typed `LandmarkDetector` Protocol); detector + classifier **entry-point registries** (`openmimicry.contracts.vision_detector` / `..._gesture_classifier` / `..._movement_classifier`) so M14 / third-party adapters can plug in without touching this package. **Default rule-based gesture classifier** (`classifiers/rules.py`) recognises `open_palm`, `fist`, `thumbs_up`, `point`, `peace`, `wave_pose` on the MediaPipe Hands skeleton. **Temporal movement classifier** (`classifiers/movements/rules.py`) recognises `wave_motion`, `raised_hand`, `nodding`, `shaking_head` from a sliding `VisionFrame` window. Optional `sklearn` and `onnx` loaders (`classifiers/{sklearn,onnx}.py`) lazy-import their heavy deps and `ClassifierUnavailable`-fail gracefully. **`MediaPipeVisionAdapter`** composes capture → detectors → classifiers → bus, with target-fps throttling, per-gesture debouncing, and a `consent_resolver` gate that refuses to start until consent is granted. **`director_mapping.py`** turns `GestureDetection` / `MovementDetection` into `AvatarDirective` overrides via `vision.gesture_map` / `vision.movement_map` (whitelisted keys only — garbage fields are dropped). **Sample profile** `config/profiles/vision.yaml` (basic + mock voice + MediaPipe vision + sample maps). **`scripts/doctor.py`** gains a `_check_vision_stack()` section that warns when OpenCV / MediaPipe / `openmimicry.vision` aren't importable; camera-probe is env-gated behind `OPENMIMICRY_DOCTOR_PROBE_CAMERA=1`. **Tests**: `tests/unit/vision/{test_throttle,test_classifiers_rules,test_movement_rules,test_mocks,test_director_mapping,test_mediapipe_adapter}.py` — throttle + debounce edge cases, every rule-based gesture against hand-crafted 21-point skeletons, every movement rule against synthetic frame windows, `MockVisionAdapter` lifecycle + Protocol satisfaction, director mapping (whitelisted keys, duration fallback, provenance metadata), and `MediaPipeVisionAdapter` end-to-end with a fake `VideoCapture` + fake hand detector (no MediaPipe import in the test path); contract test `tests/contract/test_vision.py` with a hermetic guard set to `{"mock"}`. **`Makefile`** already installed `packages/openmimicry-vision` for `PROFILE=vision`; no change needed.
- **MX (tooling baseline):** workspace `pyproject.toml` with Ruff, pyright, pytest, coverage configuration. `.pre-commit-config.yaml` with ruff + commitlint. `.editorconfig`. `Makefile` targets `lint`, `format`, `typecheck`, `test`, `ci`, `check-imports`, `validate-packs`, `pre-commit-install`. Cross-platform `scripts/doctor.py` and `scripts/check_imports.py`. GitHub Actions: `ci.yml`, `release.yml`, `codeql.yml`. Dependabot grouped weekly updates.
- **Phase 0 (contract freeze):** runnable Protocols and Pydantic schemas under `packages/openmimicry-core/src/openmimicry/core/{contracts,schemas}/`. Sibling packages (`openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, `openmimicry-tasks`) with stub `mocks.py` raising `NotImplementedError`. Contract test scaffolding in `tests/contract/` with parametrised fixtures.
- **M0 (`openmimicry-core` runtime):** `EventBus` (async fan-out with bounded queues), `RuntimeStore` (immutable snapshots), `AppConfig` loader with env-overlay + profile merge + Pydantic validation, `structlog`-based logging with bus tap, `Runtime` context manager, lifecycle helpers.
- **M1 (`openmimicry-llm`):** `MockLLMAdapter` (deterministic scripted mock, replaces Phase 0 stub), `LiteLLMAdapter` (lazy-imports LiteLLM; maps provider exceptions to typed `LLMTransportError`/`LLMAuthError`/`LLMToolCallError`), `LLMRouter` (primary + optional fallback with `RouterRetryPolicy`; never falls back on auth errors or after the primary has emitted chunks), tiny prompt registry (`openmimicry.llm.prompts.load`) with default `system_default.txt` and `system_personality.j2` Jinja2 templates. Both adapters register via the `openmimicry.contracts.llm` entry point and pass the un-skipped contract suite (`tests/contract/test_llm.py`). Optional install `pip install "openmimicry-llm[litellm]"` for the real provider stack.
- **M2 (`openmimicry-voice`):** `MockSTTAdapter` and `MockTTSAdapter` (programmable, replace Phase 0 stubs). `RealtimeSTTAdapter` wraps `RealtimeSTT.AudioToTextRecorder` behind a thread-safe `asyncio.Queue` bridge; `RealtimeTTSAdapter` wraps `RealtimeTTS.TextToAudioStream` with a centralised engine factory (`coqui` / `piper` / `azure` / `openai` / `system`). Both lazy-import their heavy deps. `SpeechController` owns the single active TTS task, the barge-in policy (waits `voice.modes.barge_in_grace_ms`, re-checks VAD), the PTT cycle (`ptt_down`/`ptt_up` publish `UserSpeechStarted` / `UserSpeechFinal`), and the live-wake projection (`enable_live_listening` / `disable_live_listening`). `WakeController` is a thin enable/disable wrapper. All adapters register via the `openmimicry.contracts.{stt,tts,speech_controller}` entry points; `tests/contract/test_{stt,tts,speech_controller}.py` are un-skipped. Optional installs `pip install "openmimicry-voice[realtimestt]"`, `[realtimetts]`, `[voice]`.
- **M3 (`openmimicry-avatar` core):** character-pack `load_pack(path)` / `validate_pack(path)` with `ValidationReport`, honouring the fallback rules in `docs/character_packs.md` §6 (missing `_speaking` → warning, base fallback; broken manifest → `PackLoadError` or report errors). `AvatarDirector` implements the state-machine table from §4 verbatim — every cell covered by parametrised tests. `AvatarOrchestrator` subscribes to the bus, dispatches directives to the active `AvatarRuntimeAdapter`, schedules hold-and-return timers for `happy` / `error`, and `swap_runtime(new)` preserves visual state by re-emitting the current directive onto the new runtime. `MockAvatarRuntimeAdapter` (replaces Phase 0 stub) is a recording mock with `directives_received` / `is_visible` / `is_speaking` / `last_text` that accepts any `AvatarDirective` without raising. Mock registers via the `openmimicry.contracts.avatar_runtime` entry point; `tests/contract/test_avatar_runtime.py` is un-skipped. `scripts/validate_pack.py` CLI wraps the validator (exit 1 on errors; `--strict` promotes warnings to errors). M4 (Sprite2D), M9 (Three.js), and the post-v0.2 modalities plug into this substrate.
- **M5 (`openmimicry-tasks`):** capability-based `TaskRouter` (preferred-runtime → capability-superset → default → `NoAdapterForCapabilities`) that itself satisfies `TaskRuntimeAdapter`. `MockTaskRuntimeAdapter` (scripted, replaces Phase 0 stub) supports `scripted_updates` and `cancel_flips_terminal=True` for deterministic test scenarios. Three concrete adapters: `LocalShellAdapter` (allowlist-or-reject: each `AllowlistEntry` declares `flag_patterns`, optional `positional_pattern`, and `max_args`; `shlex.split` parsing only, `subprocess.exec` with `shell=False`, SIGTERM→SIGKILL cancel with `cancel_grace_s`, full audit log of every accepted/rejected command); `ClaudeCodeAdapter` (spawns the `claude` CLI with a curated env — only `PATH`, `HOME`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_HOME`, plus caller-declared overrides — and parses `Wrote file:` / `Ran command:` / `Error:` lines into `TaskUpdate.note` and `Artifact` records); `MCPAgentAdapter` (lazy-imports `mcp_agent`; raises `MCPAgentUnavailable` with the install pointer when the extra is absent; tolerates `Agent.run()` returning either an async iterator or a coroutine). `OpenClawAdapter` and `PicoClawAdapter` ship as post-v0.2 stubs that raise `NotImplementedError` pointing at `docs/modules/post_v0_2_modalities.md`. Regex-first `detect_task_intent(text)` maps `ask claude to …` / `send this to claude: …` / `use the mcp agent to …` / `run shell to …` to `TaskRequest(preferred_runtime, capabilities_required)`. All adapters register via the `openmimicry.contracts.task_runtime` entry point; `tests/contract/test_task_runtime.py` is un-skipped under a hermetic guard (`mock` always; `local_shell` when `RUN_LOCAL_SHELL_CONTRACT=1`). Optional installs `pip install "openmimicry-tasks[mcp-agent]"`, `[claude-code]`, `[tasks]`.
- **M12 (`ExternalAvatarAdapter` + protocol spec + echo server):** the fifth concrete avatar modality — a renderer-agnostic WebSocket bridge that lets any third-party renderer (browser pet, Blender, Unreal, custom Unity, …) plug into OpenMimicry without baking it into the core. **Python**: `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/external/{adapter,client}.py`. `ExternalClient` is a runtime-checkable Protocol; `WSExternalClient` lazy-imports `websockets` (raising `ExternalUnavailable` with the install pointer when missing); `MockExternalClient` is the test fixture with `fail_until_attempt`, `simulate_disconnect`, and `feed_incoming`. `ExternalAvatarAdapter` mirrors the M11 shape — bounded outbound queue (drop-oldest with one-shot warning), exponential-backoff reconnect (250 ms → 5 s) that re-queues in-flight frames on send failure, reverse-channel reader that increments `acks_received` / `ready_received` and captures `errors_received`. Every adapter method encodes the additive M12 wire-protocol frame (`avatar.directive` / `load.character` / `set.visibility` / `set.text` / `shutdown`); reverse channel accepts `ready` / `ack` / `error`. `shutdown` sends a best-effort `{"type":"shutdown"}` frame before closing. Capabilities `{"external", "gestures", "gaze", "expressions"}`. Registered via `openmimicry.contracts.avatar_runtime` as `external`; optional install `pip install "openmimicry-avatar[external]"`. **Backend wiring** picks the adapter when `avatar.runtime == "external"` and forwards `config.avatar.runtimes.external` as `runtime_cfg`. **Contract test** widens the hermetic guard to `{"mock", "sprite2d", "threejs", "live3d", "unity", "external"}`; the External factory uses `MockExternalClient` so the contract suite stays offline. **Python tests** (`tests/unit/avatar/runtimes/test_external_{client,adapter}.py`): client Protocol satisfaction, send-before-connect raises, `fail_until_attempt`, `simulate_disconnect`, `feed_incoming` round-trip, `ExternalUnavailable` on missing extra; adapter Protocol + capabilities, every frame shape, healthcheck reflects client state, `shutdown` sends the shutdown frame and is idempotent, reconnect after `simulate_disconnect`, bounded-queue drop-oldest with one-shot warning, `ack`/`ready`/`error` reverse-channel counters, factory shape. **Reference echo server** (`apps/external-echo/`): tiny Node WS server (`src/server.ts`) that logs every frame and replies with `ready` on connect + `ack` per directive — wired as `@openmimicry/external-echo` in the pnpm workspace, with `OM_EXTERNAL_HOST` / `OM_EXTERNAL_PORT` env overrides. **Docs**: `docs/external_runtimes.md` is the canonical "how do I build a compliant renderer" page — wire-protocol table, browser-pet worked example (30 lines), Unity-flavour pointer to M11, testing flow against the echo server, status note (Stable for one minor cycle, additive-only).
- **M11 (`UnityAvatarAdapter` + Unity bridge sample):** the fourth concrete avatar modality, this time **external**: the OpenMimicry backend pushes `AvatarDirective`s to a separate Unity process over WebSocket, and Unity drives an `Animator` on its side. **Python**: `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/unity/{adapter,transports}.py`. `UnityTransport` Protocol with two implementations — `WSUnityTransport` (lazy-imports `websockets`; raises `UnityTransportUnavailable` with the install pointer when the optional extra is missing) and `MockUnityTransport` (records sent frames, lets tests push reverse-channel frames via `feed_incoming`). `UnityAvatarAdapter` owns a bounded outbound queue (default `maxsize=64`, drop-oldest with a one-shot warning when full), a background sender loop that reconnects with exponential backoff (250 ms → 5 s), and a background reader loop that counts `ack`s and captures `telemetry` frames. Every adapter method (`load_character`, `apply_directive`, `set_text`, `start_speaking`, `stop_speaking`, `set_visibility`) encodes the M11 additive wire-protocol frame (`avatar.directive`, `load.character`, `set.visibility`, `bubble.text`). Capabilities `{"3d", "external", "gestures", "gaze", "expressions"}`. Registered via `openmimicry.contracts.avatar_runtime` as `unity`; optional install `pip install "openmimicry-avatar[unity]"`. **Backend wiring** picks the adapter when `avatar.runtime == "unity"` and forwards `config.avatar.runtimes.unity` as `runtime_cfg`. **Contract test** widens the hermetic guard to `{"mock", "sprite2d", "threejs", "live3d", "unity"}`; the Unity adapter's factory uses `MockUnityTransport` so the contract suite stays offline. **Python tests** (`tests/unit/avatar/runtimes/test_unity_{transports,adapter}.py`): transport — Protocol satisfaction, send-before-connect raises, fail-until-attempt retries, close yields sentinel, `feed_incoming` round-trip, `UnityTransportUnavailable` on missing `websockets`; adapter — Protocol, capabilities, every frame shape, healthcheck reflecting transport state, shutdown idempotency, reconnect after `simulate_disconnect`, bounded-queue drop-oldest with a one-shot warning when Unity is unreachable, `ack` counter, telemetry capture, factory shape. **Unity sample** (`apps/unity-bridge/Assets/OpenMimicry/Scripts/`): `WSClient.cs` (System.Net.WebSockets client; background `Task` + main-thread marshalling queue; reconnect with exponential backoff; auto-acks `avatar.directive`; emits `telemetry` once per second), `Directive.cs` (JsonUtility DTOs for every frame), `AvatarController.cs` (`Animator` parameter bridge — `State`/`Emotion`/`Speaking`/`Intensity` + `Gesture` trigger; optional `Renderer` visibility toggle + UI text bubble). `apps/unity-bridge/README.md` documents the parameter table, the protocol, and Unity-version compatibility. CI does not build the Unity sample; the Python side is fully tested against `MockUnityTransport`.
- **M10 (`Live3DAvatarAdapter` + Live3D frontend runtime):** the third concrete avatar modality, composed over M9. **Python**: `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/live3d/{adapter,projection}.py`. `build_live3d_projection` reuses `build_threejs_projection` and patches `runtime: "live3d"` plus a `live` block — `{mouth_driver: amplitude|viseme|off, gaze_driver: smooth|snap|off, procedural_idle: bool, blend_window_ms, intensity}` with driver-specific sub-blocks for `amplitude` (`smoothing_ms`/`gain`/`open_curve`), `viseme` (`smoothing_ms`/`default`), and `idle` (`breathing_amplitude`/`breathing_period_ms`/`saccade_min_ms`/`saccade_max_ms`). Every config value is bounded; unknown driver names fall back to safe defaults without raising. `Live3DAvatarAdapter` declares capabilities `{"3d", "gestures", "gaze", "expressions", "mouth", "procedural_idle"}` and shares the M9 pack-load + bridge pipeline. Registered via `openmimicry.contracts.avatar_runtime` as `live3d`. **Backend wiring** picks the adapter when `avatar.runtime == "live3d"` and forwards `config.avatar.runtimes.live3d` as `runtime_cfg`. **Frontend** (`apps/desktop/frontend/src/runtimes/live3d/`): `Live3DRuntime.tsx` wraps M9's `<ThreeJSRuntime />` by composition (no changes to M9). Drivers tick on `requestAnimationFrame` (pluggable for tests): `mouth/amplitude.ts` (`createAmplitudeDriver` — Web Audio `AnalyserNode` + one-pole low-pass; pluggable `now()`), `mouth/viseme.ts` (`createVisemeDriver` — smoothed multi-key blend with a pack-supplied viseme→expression map), `idle.ts` (`createIdleDriver` — sine-wave breathing + scheduled micro-saccades, paused while a gesture clip is playing), `gaze.ts` (`createGazeDriver` — interpolated target with `setTarget` + `snap` + pack-supplied overrides), `expressions.ts` (`blendExpression` layers base emotion + server weights + amplitude mouth + viseme weights). The composed projection is forwarded to `<ThreeJSRuntime />` with `runtime: "threejs"` and merged `expressionWeights`. `runtimes/registry.ts` adds `"live3d"` so the registry covers all three modalities. **Tests**: Python unit (`tests/unit/avatar/runtimes/test_live3d_{projection,adapter}.py`) covers driver-block edge cases (unknown driver fallback, string→bool coercion, integer clamping), pack-load with a non-3D-friendly fixture, bridge-error swallowing, and Protocol satisfaction. Contract test hermetic guard widens to `{"mock", "sprite2d", "threejs", "live3d"}`. Vitest (`__tests__/{amplitude,idle,gaze,expressions}.test.ts`) drives the drivers against deterministic stubs (stubbed `AnalyserNode`, fake clock, fixed `random()` seed): smoothed amplitude ramp, breathing-wave bounds, saccade timing + pause-on-gesture, gaze interpolation + snap + pack override, expression layering precedence. No ML models; no changes to sibling Python packages other than `openmimicry-core`.
- **M9 (`ThreeJSAvatarAdapter` + Three.js frontend runtime):** the second concrete avatar modality. **Python**: `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/threejs/{adapter,projection}.py`. `build_threejs_projection(directive, pack)` is pure — it never reads from disk — and produces the additive §9 wire shape `{type:"avatar.directive", runtime:"threejs", directive, asset:{kind, url, pack_id}, clip, fallbackClips, blendWeights, expression, expressionWeights, gestureClip?, gazeTarget, intensity, fadeMs}`. The clip fallback chain is `<emotion>_<state>_speaking → <state>_speaking → <emotion>_<state> → <state> → idle` (de-duped, idle always terminal); `pick_clip(chain, available)` picks the first hit. `expression_weights(emotion, intensity)` mirrors the frontend's `expressions.ts` table (happy/sad/angry/confused/focused/worried) and returns a fresh dict scaled by clamped intensity. `resolve_asset` resolution order is runtime-cfg override → `pack.metadata.asset` → `{static_url_prefix}/{pack.id}/character.{kind}`; the kind defaults to `vrm` for VRM packs and `gltf` for everything else. `ThreeJSAvatarAdapter` mirrors `Sprite2DAvatarAdapter`'s shape (capabilities `{"3d", "gestures", "gaze", "expressions"}`); `load_character` logs a single warning when `pack.kind` isn't VRM/glTF but still loads, and `apply_directive` swallows projector + bridge failures (M4 rule: never raise on a well-formed directive). Registered via `openmimicry.contracts.avatar_runtime` as `threejs`. **Backend wiring** (`apps/backend/.../wiring.py`) now selects the adapter when `avatar.runtime == "threejs"`, passing `config.avatar.runtimes.threejs` through as `runtime_cfg`. **Contract test** (`tests/contract/test_avatar_runtime.py`) widens the hermetic guard to `{"mock", "sprite2d", "threejs"}` and resolves `load_character` against the shared `tests/fixtures/packs/good_pack` so all three adapters round-trip with the same parametrised body. **Python unit tests** (`tests/unit/avatar/runtimes/test_threejs_{projection,adapter}.py`): every projector helper exhaustively (clip fallback, pick_clip, expression weights scaling, asset resolution order, gesture allowlist + per-pack remap) plus adapter end-to-end against a `FakeBridge` covering apply_directive / start-stop speaking / set_text / visibility / dropped publishes / pack-load with a non-Three-friendly kind. **Frontend**: `apps/desktop/frontend/src/runtimes/threejs/`. `expressions.ts` (`resolveExpression`, `mergeWeights`), `clips.ts` (`pickClip`, `pickGestureClip`, `clipFallbackChain`), `scene.ts` (`createScene`, `configureCamera`, `attachLighting` with `studio`/`outdoor`/`flat` presets; pluggable renderer factory for tests), `vrm.ts` + `gltf.ts` (duck-typed `CharacterController` interface — VRM expression manager wired through when present, plain glTF is a no-op), `ThreeJSRuntime.tsx` (mounts under `<AvatarHost>`, async asset load with cancel-on-unmount, dispatches `playClip` + `setExpression` + `setGazeTarget` on every directive, layers gesture clip on top, exposes load-error label). Registry (`apps/desktop/frontend/src/runtimes/registry.ts`) adds `"threejs"` so `setRuntime`/`getRuntime` covers it. `package.json` adds `three`, `@types/three`, `@pixiv/three-vrm`. **Vitest** tests (`__tests__/{expressions,clips,scene,ThreeJSRuntime}.test.{ts,tsx}`): expression scaling + clamping, clip selection edge cases, scene helpers with a fully-stubbed `three` (`vi.mock`), and the React component with injected loaders proving directive → controller dispatch and unmount cleanup. **Demo pack** `characters/octomimic_vrm/` (manifest + `preview.png` + README explaining how to drop in a real `octomimic.vrm`). Bundle size delta documented in the PR body.
- **M8 (`apps/desktop/src-tauri`):** the Rust/Tauri shell. New `apps/desktop/src-tauri/` package (`openmimicry-desktop`, Tauri 2.x, `tauri-plugin-global-shortcut`). `tauri.conf.json` declares two windows: `overlay` (transparent, decoration-less, always-on-top, click-through default, `skipTaskbar: true`, `/#/overlay`) and `panel` (decorations, resizable, `visible: false`, `/#/panel`). CSP scoped to localhost backend (`http://127.0.0.1:8000` + `ws://127.0.0.1:8000`). Capabilities exposed: window minimise/close/hide/show/focus, `set-ignore-cursor-events`, `set-position`, `set-size`, `set-always-on-top`, event emit/listen, and `global-shortcut:default`. Rust modules (`src/{overlay,commands,tray,hotkeys,state,lib,main}.rs`): `overlay::set_interactive` calls `set_ignore_cursor_events(!interactive)` per `docs/desktop_overlay.md` §2 (whole-window only — no per-pixel hit testing); `overlay::clamp_to_monitor` + `overlay::safe_corner` keep the saved position on-screen when monitors change. `state::AppState` persists overlay position, current emotion, runtime name, panel visibility, and interactive flag to `<data_dir>/state.json` via tmp-file-then-rename. `tray::emotion_to_color` maps `idle → grey, listening → cyan, thinking → amber, speaking → green, happy → yellow, error → red`; `tray::render_mood_pixel` draws a 16×16 anti-aliased RGBA circle; the tray listens to the frontend's `avatar.emotion` event and re-renders the icon. `hotkeys::parse_shortcut` parses `ctrl+shift+m`-style specs into `(Modifiers, Code)`; `register_defaults` wires `Ctrl+Space` press/release → `ptt.down`/`ptt.up` events, `Ctrl+Shift+M` → toggle overlay interactive, `Ctrl+Shift+O` → toggle panel. `commands` exposes `set_overlay_interactive`, `swap_avatar_runtime`, `show_panel`, `hide_panel`, `move_overlay_to_saved_position`, `save_overlay_position`, `overlay_info`, `quit_app` — every command is `#[tauri::command]` with `Result<T, String>` return type. `lib::run()` is the canonical builder; `main.rs` is two lines. Tests (`tests/test_{overlay,state,tray,hotkeys}.rs` + in-source `#[cfg(test)]`): clamp math, safe-corner fallback, state save/load + atomic rename, emotion-to-colour table, mood-pixel buffer shape, shortcut-spec parser (including whitespace tolerance + digit keys + `cmd` aliased to `Super`). `Makefile` gains `desktop-m8`, `desktop-m8-build`, `desktop-m8-test`. The legacy `src-tauri/` (and `make desktop`) stay during the migration and will be removed once the prototype is retired.
- **M7 (`apps/desktop/frontend`):** the React/Vite application. New `package.json` at `@openmimicry/desktop-frontend` (pnpm 11.x, strict TypeScript, Vitest with `jsdom`); `vite.config.ts` proxies `/ws`, `/api`, `/static` to `http://localhost:8000`. WS client: `src/ws/protocol.ts` declares the discriminated union mirroring `contracts.md` §9 verbatim (`avatar.directive` / `transcript.preview` / `bubble.text` / `task.card` / `system.notice` server-side; `user.text` / `ptt.down` / `ptt.up` / `mode.toggle` / `task.cancel` client-side). `src/ws/reconnect.ts` is a pluggable jittered exponential-backoff controller (`initialMs` -> doubles, capped at `maxMs`, ±`jitterRatio` jitter, optional `maxAttempts`). `src/ws/WSProvider.tsx` exposes `{status, lastMessage, send, subscribe, reconnect}` and accepts a `socketFactory` for test injection; `src/ws/mockSocket.ts` ships the `MockWebSocket` tests inject. Hooks: `useWS`, `useAvatarDirective` (latest directive), `useBubbleText` (partials accumulate; `listening` clears), `useTaskCards` (`Map<handle.id, TaskUpdate>` + `cancel(id)`), `useTauriCommand` (lazy `@tauri-apps/api/core::invoke` wrapper; no-op when running in pure browser). Registry: `runtimes/registry.ts` gains `setRuntime(name, component)`, `getRuntime(name)`, and a `PlaceholderRuntime` fallback. Components: `<AvatarHost>` (reads `useAvatarDirective`, looks up registry, passes the message down as `projection`), `<SpeechBubble>`, `<TextInput>` (Enter sends `user.text`), `<VoiceToggle>` (mode.toggle; snaps to server-published config diffs), `<TaskCard>` (cancel button sends `task.cancel`), `<ModeIndicator>`, `<SettingsPanel>` (POST `/pack/swap` + `/runtime/swap`). Routes: `<OverlayRoute>` (transparent host: AvatarHost + SpeechBubble), `<PanelRoute>` (text input, voice toggles, task feed, settings); `App.tsx` wires both under `HashRouter` inside a single `WSProvider`. Styles: `styles/{overlay,panel}.css`. Vitest tests: `WSProvider.test.tsx` (open, dispatch, send, reconnect after `_serverClose`, malformed-JSON tolerance), `reconnect.test.ts` (backoff math), `AvatarHost.test.tsx` (registry lookup, unknown-runtime fallback, `defaultRuntime`, runtime swap), `SpeechBubble.test.tsx` (partial accumulation, listening-state reset), `TaskCard.test.tsx` (per-handle updates, cancel button hidden on terminal status, click sends `task.cancel`). `pnpm-workspace.yaml` already lists both `frontend/` (legacy) and `apps/desktop/frontend/`; the legacy app stays until M8 migrates the Tauri shell.
- **M6 (`apps/backend`):** the running FastAPI process. `apps/backend/src/openmimicry_backend/wiring.py` is the **single** file in the repository that imports concrete adapter classes (`MockLLMAdapter`/`LiteLLMAdapter`, `MockSTTAdapter`/`RealtimeSTTAdapter`, `MockTTSAdapter`/`RealtimeTTSAdapter`, `MockAvatarRuntimeAdapter`/`Sprite2DAvatarAdapter`, `MockTaskRuntimeAdapter`/`LocalShellAdapter`/`ClaudeCodeAdapter`/`MCPAgentAdapter`, `TaskRouter`); every other file in the backend reads them via Protocols from `openmimicry.core.contracts`. `scripts/check_imports.py` allowlist entry covers `wiring.py`. `build_runtime(config, ws_bridge=...)` returns a `Wiring` dataclass; `lifespan()` starts the speech controller + avatar orchestrator and enforces a 2 s graceful shutdown budget. `projection.py` exhaustively maps every `RuntimeEvent` variant to the §9 wire schema (`avatar.directive` flows through the avatar runtime's `WSBridge`; this projector emits `transcript.preview`, `bubble.text`, `task.card`, `system.notice`). `ws.py` provides `BroadcastBridge` (a multicast `WSBridge` for the Sprite2D adapter) and the `/ws` endpoint that subscribes to the bus, projects each event, and dispatches inbound `user.text` / `ptt.down|up` / `mode.toggle`. HTTP routes: `POST /chat` (intent-classified — task vs. LLM path; returns 202 and delivers updates over WS), `GET /health` (per-family adapter healthchecks with a 2 s timeout each), `POST /mode/toggle` (`live_wake` + `agent_voice`), `POST /pack/swap`, `POST /runtime/swap`, `POST /admin/reload`, `GET /config` (debug-gated by `OPENMIMICRY_DEBUG=1`). `make backend-m6` runs the new process; the legacy `make backend` stays during the prototype-to-package migration. Integration tests (`tests/integration/backend/`): `test_chat_flow.py`, `test_ptt_flow.py`, `test_wake_flow.py`, `test_task_flow.py`, `test_ws_projection.py`, `test_health.py`, with `tests/fixtures/configs/integration.yaml` (mocks-only). `apps/backend/src` is now included in pyright + coverage; `apps/desktop` (Tauri shell) remains excluded.
- **M4 (`Sprite2DAvatarAdapter` + frontend runtime):** the first concrete `AvatarRuntimeAdapter`. `build_sprite2d_projection(directive, pack)` produces the `avatar.directive` wire message defined in `docs/contracts.md` §9 (`{type, runtime, directive, frames, fps, loop}`); honours the `emotion + emotion_speaking` fallback rule (`speaking=True` uses `speaking_frames` when present, otherwise falls back to base) and the `default_state` fallback for unknown states (warning logged once per unknown state). `Sprite2DAvatarAdapter` publishes via an injected `WSBridge` (M6 supplies the real one; tests use a `FakeBridge`) and accepts any well-formed `AvatarDirective` without raising — `gesture` / `gaze` / `intensity` are ignored by design. Registered via the `openmimicry.contracts.avatar_runtime` entry point as `sprite2d`. Frontend: `apps/desktop/frontend/src/runtimes/sprite2d/{Sprite2DRuntime.tsx, preloader.ts, index.ts}` plus `runtimes/registry.ts`. `Sprite2DRuntime` renders the first frame on mount, advances at the projection's fps via `setInterval`, wraps when `loop=true` and clamps when `loop=false`, resets the frame index when the frame set changes. `preloader.ts` caches images in a `Map<string, HTMLImageElement>` so a second `preload([...])` with overlapping URLs only fetches the new ones. Vitest tests use fake timers + a stubbed `Image` constructor to prove the timing. Python contract test un-skipped for `sprite2d` (the null-bridge entry-point variant satisfies the hermetic guard).
- **Documentation:** `MAINTAINERS.md`, `CODE_OF_CONDUCT.md`, refreshed `CONTRIBUTING.md`, 15 GitHub issue templates spawning every module brief.

### Changed

- Project version moved from `0.1.0` → `0.2.0a0`.
- `Makefile`: added quality-floor and packaging targets while preserving the prototype's `backend`/`frontend`/`desktop` targets.
- `pyproject.toml`: switched profile names (`basic|voice|threejs|live3d|unity|agent|full|studio|dev`) to mirror the YAML profiles documented in [`docs/configuration.md`](docs/configuration.md) §6.
- **Supply-chain hardening:** the JS workspace moves from npm to **pnpm 11.x**. New root files: `.npmrc`, `pnpm-workspace.yaml`, root `package.json` with `packageManager: pnpm@11.0.0` and `engine-strict`. Three controls are enforced by `.npmrc`: `minimum-release-age=14` (refuse packages published in the last 14 days), `block-exotic-subdeps=true` (no git/tarball/file transitive deps), and `ignore-scripts=true` with an explicit `onlyBuiltDependencies` allowlist (postinstall scripts blocked by default). Full policy in [`SECURITY.md`](SECURITY.md). `Makefile` targets: `frontend-install`, `frontend-audit`, `frontend-approve-builds`. CI installs pnpm 11 via `pnpm/action-setup@v4` and runs `pnpm audit` on every PR. Dependabot restricted to non-major bumps so `minimum-release-age` can catch poisoned versions.

### Documentation

- Full module briefs under `docs/modules/`: Phase 0 + MX + M0..M9 + post-v0.2 (M10–M12).
- **M13 (vision, post-v0.2, optional):** new brief `docs/modules/M13_vision.md` for a camera-driven `MediaPipeVisionAdapter` + `GestureClassifier` registry that publishes `GestureDetected` events the avatar director maps to `AvatarDirective` overrides. Off by default, opt-in via `pip install openmimicry[vision]` and `vision.enabled: true`. Privacy-first: no upload, explicit consent dialog on first activation. `pyproject.toml` gains `vision` and `full-vision` extras; `Makefile` lists them under `make install PROFILE=…`. Implementation deferred — the contract surface (`VisionAdapter`, `GestureClassifier`, `HandLandmark`/`HandPose`/`GestureDetection`/`VisionConfig` schemas, three new `RuntimeEvent` variants) lands in a contracts-amendment PR before M13 begins.
- Architecture, adapter, event-flow, voice-mode, task-delegation, character-pack, desktop-overlay, configuration, testing-and-ci, and migration docs.

[Unreleased]: https://github.com/ghenrique/openmimicry/compare/v1.3.2...HEAD
[1.3.2]: https://github.com/ghenrique/openmimicry/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/ghenrique/openmimicry/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/ghenrique/openmimicry/compare/v1.2.2...v1.3.0
[1.2.2]: https://github.com/ghenrique/openmimicry/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/ghenrique/openmimicry/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/ghenrique/openmimicry/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ghenrique/openmimicry/compare/v1.0.0...v1.1.0
