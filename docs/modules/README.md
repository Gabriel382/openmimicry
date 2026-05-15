# OpenMimicry module briefs

This folder is the operational manual for building OpenMimicry in parallel. Each `Mx_*.md` file is a **self-contained brief** that one contributor — Claude, another LLM, or a human — can pick up without reading the rest of the codebase, implement, and merge.

The guarantee that lets this work: every brief depends only on the **frozen contracts** in [`../contracts.md`](../contracts.md) and on `openmimicry-core` itself. No brief imports from sibling packages; siblings are consumed through **mocks**.

If you are picking up a brief, you only need three documents in front of you:

1. [`../contracts.md`](../contracts.md) — the immutable interface set. Treat it as read-only.
2. The brief itself, e.g. `M1_llm.md`.
3. The one architecture doc the brief points you at (e.g. `../adapters.md` for adapters, `../voice_modes.md` for voice).

Anything else (sibling source, other modules' docs) is optional context. The brief is sufficient.

## The brief template

Every file in this folder follows this structure verbatim, as defined in [`../parallel_execution.md`](../parallel_execution.md) §4:

```text
# Module Mx: <name>

## Goal (1 line)
## Scope and non-scope
## Inputs (immutable, from contracts.md)
## Outputs (this module owns)
## Mock implementations this module provides
## Test surface
## Step-by-step plan (atomic, numbered)
## Definition of done (checklist)
## Recommended LLM brief (copy-pasteable prompt)
```

The **Recommended LLM brief** at the bottom of each file is the single block of text you paste into a fresh LLM session. It cites the exact files to read, the exact files to write, and the exact "done" criteria.

## Module list

| File | Module | Owns | Depends on (contracts) | Status |
|---|---|---|---|---|
| [`M_phase0_contract_freeze.md`](./M_phase0_contract_freeze.md) | Phase 0 | `contracts.md` → code: Protocols, schemas, mocks, contract tests | nothing | foundation |
| [`MX_tooling.md`](./MX_tooling.md) | Cross-cutting | Ruff, pyright, pytest, pre-commit, CI, release pipeline | nothing | runs in parallel with any module |
| [`M0_core.md`](./M0_core.md) | `openmimicry-core` | `AppConfig` loader, `EventBus` impl, `RuntimeStore`, logging, lifecycle | Phase 0 | blocks all `Mx` |
| [`M1_llm.md`](./M1_llm.md) | `openmimicry-llm` | `LiteLLMAdapter`, `LLMRouter`, `MockLLMAdapter` | Phase 0, M0 | parallel with M2, M3, M5 |
| [`M2_voice.md`](./M2_voice.md) | `openmimicry-voice` | `RealtimeSTTAdapter`, `RealtimeTTSAdapter`, `SpeechController`, `WakeController`, mocks | Phase 0, M0 | parallel with M1, M3, M5 |
| [`M3_avatar_core.md`](./M3_avatar_core.md) | `openmimicry-avatar` (core) | Pack loader/validator, `AvatarDirector`, `AvatarOrchestrator`, `MockAvatarRuntimeAdapter` | Phase 0, M0 | blocks M4, M9 |
| [`M4_avatar_sprite2d.md`](./M4_avatar_sprite2d.md) | `Sprite2DAvatarAdapter` | Image-sequence runtime, frontend bridge | Phase 0, M0, M3 | parallel with M5, M6 once M3 lands |
| [`M5_tasks.md`](./M5_tasks.md) | `openmimicry-tasks` | `TaskRouter`, mcp-agent / Claude Code / local-shell adapters, mocks | Phase 0, M0 | parallel with M1, M2, M3 |
| [`M6_backend.md`](./M6_backend.md) | `apps/backend` | FastAPI process, wiring, WebSocket projection, `/health`, `/chat` | All `Mx` mocks | assembly module |
| [`M7_frontend.md`](./M7_frontend.md) | `apps/desktop/frontend` | React/Vite, overlay/panel routes, WS client, frontend `AvatarRuntimeAdapter` registry | Phase 0 wire protocol | parallel with everything Python |
| [`M8_tauri.md`](./M8_tauri.md) | `apps/desktop/src-tauri` | Two windows, click-through, tray, global hotkeys, IPC commands | Phase 0 wire protocol | parallel with M7 |
| [`M9_avatar_threejs.md`](./M9_avatar_threejs.md) | `ThreeJSAvatarAdapter` | In-overlay 3D renderer, VRM/glTF, clip selection | Phase 0, M3, M7 | post-v0.2, parallel with M10–M12 |
| [`post_v0_2_modalities.md`](./post_v0_2_modalities.md) | M10 / M11 / M12 | Live3D, Unity bridge, External | Phase 0, M3, M7 | post-v0.2 |
| [`M13_vision.md`](./M13_vision.md) | `openmimicry-vision` *(optional)* | `MediaPipeVisionAdapter`, `GestureClassifier` registry, gesture → AvatarDirective mapping | Phase 0 (contracts amendment), M3 | post-v0.2, optional install (`pip install openmimicry[vision]`) |

## Interface stability policy

This is the single most important rule of the parallel plan. Everything else flows from it.

Every symbol in `../contracts.md` carries one of three stability tags. Each tag has a different change protocol:

- **Frozen.** Cannot change for the lifetime of `schema_version: 1`. Examples: `LLMAdapter.generate`, `AvatarRuntimeAdapter.apply_directive`, `AvatarDirective.state`, the `RuntimeEvent` union member names. The only path to change is a coordinated PR that bumps `schema_version` to 2 and migrates every consumer.
- **Stable.** May gain new optional fields or new optional methods between minor versions. Cannot remove or rename. Example: adding `intensity` was a stable change; renaming it would not be. Stable additions require a `contracts:` PR.
- **Provisional.** Marked with a `# provisional` comment in `contracts.md`. May change between any two minor versions if all consumers are notified. There should be very few of these, and they should graduate to **Stable** before v1.0.

By default, every Protocol, schema, and wire-protocol message type in `contracts.md` is **Frozen**. The exceptions are tagged explicitly.

## How to add a new module

1. Pick the next available `Mn` (or descriptive name).
2. Add a row to the table above.
3. Copy the template from `parallel_execution.md` §4 into `docs/modules/Mn_<name>.md`.
4. Fill in every section. If you can't fill `## Inputs`, you don't know enough yet — go read `contracts.md`.
5. Open a PR `docs(modules): add Mn brief` and merge.
6. Anyone (you, another agent) can then claim it.

## Don't

- **Don't write production code in `apps/backend` or `apps/desktop` that imports from sibling `packages/*` source.** Imports must go through `openmimicry-core.contracts`. The CI step `scripts/check_imports.py` enforces this.
- **Don't edit `contracts.md` to fix a module.** If the contract has a gap, that's a Phase 0 amendment PR. Land it first.
- **Don't conflate modules.** If your PR touches two `Mx` directories outside of `apps/backend/wiring.py` and `apps/desktop/frontend/src/runtimes/`, you're doing something wrong.

## Do

- **Do** ship the mock first. Other modules will depend on it.
- **Do** write the contract test before the implementation. The test is the executable spec.
- **Do** treat the "Recommended LLM brief" at the bottom of your module file as the actual prompt you'd hand to a fresh agent. If it isn't self-sufficient, sharpen it.
- **Do** open a `contracts: amendment` PR the moment you find a gap. Stop, fix, resume.

## Reading order for a new contributor

If you are coming to OpenMimicry fresh:

1. `../architecture.md` — 10 minutes, gets the model in your head.
2. `../contracts.md` — 15 minutes, this is what you'll be coding against.
3. `../parallel_execution.md` — 5 minutes, how we work.
4. The brief for the module you'll implement.
5. Optional: the relevant architecture sub-doc (`../adapters.md`, `../voice_modes.md`, `../avatar_modalities.md`, `../task_delegation.md`, `../desktop_overlay.md`).

Total time before first commit: under an hour.
