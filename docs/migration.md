# Migration plan

This is an **incremental** plan. The current prototype keeps running on `main` throughout. Each phase introduces new structure side-by-side with the existing folders; the old folders are deleted only after the new home reaches feature parity for that area.

The current top-level layout, for reference:

```text
apps/  avatar/  backend/  backends/  characters/  config/  core/
docs/  frontend/  packs/  profiles/  scripts/  src-tauri/  tests/  tts/
README.md  ROADMAP.md  Milestone.md  Makefile  pyproject.toml
```

Target layout is in [`architecture.md`](./architecture.md) §3.

## Phase guide

Each phase has: goal, ships when, what changes, and what stays untouched.

### P0 — Tooling baseline (1–2 days)

**Goal.** Make the repo lintable, type-checked, and tested before any structural change. Cheapest, highest-trust win.

**Ships when.** `make ci` passes locally on a fresh clone, and CI is green on a PR that changes nothing else.

Changes:

- Add `pyproject.toml` `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage.*]` blocks.
- Add `pyrightconfig.json` (basic mode for now).
- Add `.github/workflows/ci.yml` running ruff, pyright, pytest on Ubuntu and Windows, Python 3.11 + 3.12.
- Add `.pre-commit-config.yaml` with ruff and `commitlint`.
- Add `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` (if missing), refresh `CONTRIBUTING.md`.
- Add Conventional Commits guidance to `CONTRIBUTING.md`.

Untouched: `core/`, `backends/`, `avatar/`, `tts/`, `backend/`, `frontend/`, `src-tauri/`.

### P1 — `openmimicry-core` extraction (2–4 days)

**Goal.** Move config loading, event bus, schemas, and runtime store into a typed, tested package.

**Ships when.** `packages/openmimicry-core/` is published as a local workspace dep, `apps/backend` imports from it, and the legacy `core/` directory is removed.

Changes:

- Create `packages/openmimicry-core/` with its own `pyproject.toml`.
- Define `AppConfig`, `RuntimeEvent` union, `AvatarDirective`, `Emotion`, etc. in `openmimicry.core.schemas`.
- Implement `EventBus`, `RuntimeStore`, structured logging, config loader, hot reload.
- Move equivalent code from existing `core/` and `config/` over file by file. Each move is its own commit, each commit keeps tests green.
- Switch `apps/backend` (still at `backend/`) to import from `openmimicry.core.*`.
- Delete `core/` after parity.

Untouched: `backends/`, `avatar/`, `tts/`, `frontend/`, `src-tauri/`.

### P2 — `openmimicry-llm` with LiteLLM (2–3 days)

**Goal.** One `LLMAdapter` contract; LiteLLM is the first implementation.

**Ships when.** The legacy `backends/` directory is empty, the chat endpoint streams via `LLMRouter`, and `tests/unit/llm/` covers contract + router.

Changes:

- Create `packages/openmimicry-llm/`.
- Define `LLMAdapter`, `LLMRouter`, `MockLLMAdapter`.
- Implement `LiteLLMAdapter` wrapping `litellm.acompletion(..., stream=True)`.
- Replace `backends/` usage in `backend/app/llm` with `LLMRouter`.
- Delete `backends/`.

### P3 — `openmimicry-voice` with RealtimeSTT + RealtimeTTS (3–5 days)

**Goal.** Voice runs through `SpeechController` + adapters. Existing `tts/` and `backend/app/tts/` experiments are replaced.

**Ships when.** Text input, PTT, wake-name live mode all route through the new controller; barge-in works against the mock STT; the legacy `tts/` directory is removed.

Changes:

- Create `packages/openmimicry-voice/` with `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController`.
- Implement `RealtimeSTTAdapter` and `RealtimeTTSAdapter`.
- Implement `MockSTTAdapter` and `MockTTSAdapter` for CI.
- Wire `SpeechController` into `apps/backend` and into the WebSocket projection.
- Migrate `frontend/src/voice` and `frontend/src/tts` to consume the new event projection only (no direct calls).
- Delete `tts/` and `backend/app/tts/`.

### P4 — Avatar baseline: `AvatarRuntimeAdapter` + Sprite2D (3–5 days)

**Goal.** Pack loader, validator, director state machine, **`AvatarRuntimeAdapter` contract**, and the Sprite2D reference implementation. This is the phase that earns the "pluggable avatar layer" framing.

**Ships when.** Both shipped packs (`octomimic`, `mimic_blue`) load through the new validator; `scripts/validate_pack.py` works; the legacy top-level `avatar/` is removed; the runtime emits the normalized `AvatarDirective` and the Sprite2D adapter consumes it via the WebSocket projection.

Changes:

- Create `packages/openmimicry-avatar/`.
- Define `CharacterPack`, `PackSchema`, `AvatarDirector`, `AvatarOrchestrator`.
- Define `AvatarRuntimeAdapter` Protocol and the normalized `AvatarDirective` schema (state, emotion, animation, speaking, text, next_state, duration_ms, intensity, gesture, gaze, metadata).
- Implement `Sprite2DAvatarAdapter` and `MockAvatarAdapter`.
- Verify the `emotion + emotion_speaking` convention against existing pack folders.
- Add `scripts/validate_pack.py` and `tests/contract/test_avatar_runtime.py`.
- Migrate `packs/manifests/*` into the new pack manifest format if needed; otherwise keep `characters/` as the canonical packs folder.
- Delete `avatar/` once the orchestrator is wired in.

### P5 — `openmimicry-tasks` with mcp-agent + Claude Code (3–5 days)

**Goal.** First two task adapters work end-to-end; router routes by capability.

**Ships when.** "Ask Claude to refactor `utils.py`" produces a TaskHandle, streams updates to the panel, and ends in a `happy` directive.

Changes:

- Create `packages/openmimicry-tasks/`.
- Implement `TaskRequest`, `TaskHandle`, `TaskUpdate` schemas.
- Implement `TaskRouter`, `MockAdapter`, `mcp_agent_adapter`, `claude_code_adapter`, `local_shell_adapter` (allowlisted).
- Wire LLM tool-calls and a tiny intent classifier in `apps/backend`.

### P6 — Backend rewire (1–2 days)

**Goal.** `apps/backend/` imports only from `packages/*`. No business logic lives in the app.

**Ships when.** Removing `apps/backend/` would leave only HTTP transport in the codebase; everything else is in `packages/`.

Changes:

- Move `backend/app/main.py` to `apps/backend/main.py`.
- Replace anything that still imports from the old `backend/app/*` with `packages/openmimicry-*`.
- Delete `backend/` once new path works.
- Update `Makefile` paths.

### P7 — Desktop polish (2–4 days)

**Goal.** Two-window topology, click-through default, tray icon, global hotkeys, fit-to-character mode.

**Ships when.** A screenshot exists with the octomimic avatar on top of a code editor, the panel open beside it, and the click-through indicator visible.

Changes:

- Refactor `src-tauri` to define two windows (`overlay`, `panel`).
- Add `set_overlay_interactive` Tauri command.
- Add tray icon with mood pixel + menu.
- Add global hotkeys (PTT, toggle interact, show/hide panel).
- Add an `ui.overlay.fit_to_character` mode.
- Rust + Vitest tests for the toggles.

### P8 — Release v0.2.0 (1 day)

**Goal.** Tagged, polished, screenshotted, install-tested. The release ships Sprite2D, voice, LLM, and task delegation — the other modalities are advertised on the roadmap, not in the release notes.

**Ships when.** The GitHub Release exists with Windows + Linux bundles, the README has the screenshot, and `pip install openmimicry[basic]` works.

Changes:

- Refresh `README.md` per [`readme_guide.md`](./readme_guide.md).
- Run `make ci` clean on a fresh container.
- Tag `v0.2.0`, push, watch release workflow build artifacts.
- Cut a GitHub Discussions post inviting contributors.

### P9 — Modality: Three.js + VRM / glTF (4–6 days)

**Goal.** Lightweight 3D inside the overlay window. No second app, no native engine.

**Ships when.** `avatar.runtime: threejs` loads a `.vrm` or `.glb` file and animates it through `idle / listening / thinking / speaking / happy / error`. Swap at runtime via `AvatarOrchestrator.swap_runtime` works.

Changes:

- `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/threejs/` — thin Python adapter that resolves assets and forwards directives to the frontend over a dedicated WS channel.
- `apps/desktop/frontend/src/runtimes/threejs/` — Three.js renderer with VRM loader, glTF loader, transparent background, configurable camera + lighting.
- `[threejs]` extras + `config/profiles/threejs.yaml`.
- Contract test plus a Vitest fixture stream.

### P10 — Modality: Live 3D (3–5 days)

**Goal.** Live 3D adds blending, mouth-from-TTS, gaze, and gesture on top of the Three.js renderer.

**Ships when.** A 30-second demo where the avatar's mouth follows TTS amplitude and the gaze tracks the current speech-bubble subject.

Changes:

- `Live3DAvatarAdapter` reuses Three.js but plugs in `MouthDriver`, `GazeDriver`, `BlendController`.
- Extends the `apply_directive` path to use `intensity`, `gesture`, `gaze`, `duration_ms`.
- `[live3d]` extras + `config/profiles/live3d.yaml`.
- Mock contract tests for the controllers; an integration test that asserts the directive parameters end up in the renderer state.

### P11 — Modality: Unity bridge (5–8 days, partly Unity-side)

**Goal.** A documented protocol and a working sample Unity project under `apps/unity/`.

**Ships when.** The sample Unity scene reflects `AvatarDirective`s from OpenMimicry: state changes drive Animator states, `gesture` triggers events, `gaze` updates a parameter.

Changes:

- `UnityAvatarAdapter` (Python) sending JSON directives over WebSocket with reconnect logic.
- `apps/unity/` sample project (separate `README.md`, separate CI job, not in the Python install).
- Protocol doc in `docs/avatar_modalities.md` §1.5 expanded with the JSON message catalog.
- `[unity]` extras + `config/profiles/unity.yaml`.

### P12 — Modality: External transport (2 days)

**Goal.** A generic adapter for third-party renderers (VTube Studio-style, Blender preview, Unreal, browser-based avatars).

**Ships when.** Documentation + a worked example: a tiny demo external renderer in the `examples/` folder that subscribes to `AvatarDirective`s.

Changes:

- `ExternalAvatarAdapter` (transport-only; the runtime is owned by the third party).
- `examples/external-renderer/` demo (Node or Python WS client logging directives).
- Section in `docs/avatar_modalities.md` §1.6 with the JSON wire format, framing rules, reconnect semantics.

## Cross-cutting hygiene during the migration

- One PR per phase, broken into reviewable commits.
- Every phase updates `CHANGELOG.md` under `## Unreleased`.
- Every phase adds at least one integration test that exercises the new package.
- No phase introduces an import from `packages/<a>` into `packages/<b>` that violates the dependency table in [`architecture.md`](./architecture.md) §4.

## Rollback strategy

If a phase reveals a bad assumption, rollback is trivial because the legacy code still sits next to the new code. Revert the PR, file an issue with the failure mode, and the prototype on `main` still works.

## Order rationale

LLM comes before voice because the chat path is the simplest end-to-end. Voice comes before avatar because the avatar state machine needs `RuntimeEvent`s that voice produces. Tasks come last in `packages/*` because they piggyback on the LLM tool-call surface. Backend rewire is its own phase to keep the diffs small. Desktop polish is last because it benefits from already-stable contracts.

## Time estimate

Realistic part-time, P0–P8 only (sprint to v0.2.0 release with Sprite2D): ~3–4 weeks. Aggressive full-time: ~10–12 working days. The estimate is dominated by P3 (voice) and P5 (tasks) because both interact with external libraries with their own gotchas.

P9–P12 (the other modalities) are post-v0.2.0 work. Together they add roughly another 2–3 weeks part-time; they can land independently and each one is its own release (v0.3, v0.4, etc.). The phased order is deliberate: ship Sprite2D first, prove the `AvatarRuntimeAdapter` contract holds, *then* light up Three.js, Live 3D, Unity, and the external transport. That way every new modality is a confirmation of the architecture, not a stress test of it.
