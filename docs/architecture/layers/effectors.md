# Layer: Effectors / Actors

Anything that **acts** on the user or the world. Pure outputs.
Effectors consume directives + task requests from the cognition
layer and produce: rendered avatar frames, spoken audio, shell
output, agent task progress, …

## Packages

| Package | What it does | Status |
|---------|--------------|--------|
| [`openmimicry-tts`](../../../packages/openmimicry-tts/) | Text → speech audio (`MockTTSAdapter`, `RealtimeTTSAdapter` over RealtimeTTS) | Facade over the TTS half of `openmimicry-voice`. |
| [`openmimicry-avatar`](../../../packages/openmimicry-avatar/) | Render the avatar in five modalities: Sprite2D, Three.js/VRM, Live3D, Unity, External | Native. Includes the AvatarOrchestrator and director state machine (cognition) too — those live with their state. |
| [`openmimicry-tasks`](../../../packages/openmimicry-tasks/) | Run external agents — `LocalShellAdapter` (allowlist-only), `ClaudeCodeAdapter` (CLI), `MCPAgentAdapter`, all behind a capability-based `TaskRouter` | Native. |

## Contracts they satisfy

- `openmimicry.core.contracts.voice.TTSAdapter`
- `openmimicry.core.contracts.avatar.AvatarRuntimeAdapter`
- `openmimicry.core.contracts.tasks.TaskRuntimeAdapter`

## What lives here

- 5 concrete avatar runtimes (Sprite2D, Three.js, Live3D, Unity,
  External) plus the registries that mount the right one.
- 4 concrete task runtimes (Mock, LocalShell, ClaudeCode, MCPAgent)
  plus the `TaskRouter` that selects between them.
- TTS adapters (Mock, RealtimeTTS-over-Coqui/Piper/Azure/OpenAI/system).

## What doesn't live here

- STT — that's a sensor (`openmimicry-stt`).
- The director state machine — that's cognition (lives in
  `openmimicry-avatar` next to its directives).
- The `SpeechController` — coordinates STT + TTS so it sits in
  the voice package.

## Develop it in isolation

```bash
# Three.js avatar only — no real WebGL needed, vi.mock("three") in Vitest
cd apps/desktop/frontend
pnpm --filter @openmimicry/desktop-frontend exec vitest run src/runtimes/threejs

# Python adapter side
cd packages/openmimicry-avatar
.venv\Scripts\python -m pytest tests/unit/avatar/runtimes/test_threejs_adapter.py -q

# LocalShell adapter only (POSIX hosts; Windows skips the live test)
cd packages/openmimicry-tasks
.venv\Scripts\python -m pytest tests/unit/tasks/test_local_shell_adapter.py -q
```

Every effector ships a mock so the test you're writing in *one*
package doesn't pull the whole stack with it.

## Adding a new effector — worked example: a new avatar modality

The five existing modalities (Sprite2D, Three.js, Live3D, Unity,
External) all follow the same template, documented in
[`../../modules/M9_avatar_threejs.md`](../../modules/M9_avatar_threejs.md).
The 17-step plan there is the canonical reference.

Summary:

1. Implement `openmimicry.core.contracts.avatar.AvatarRuntimeAdapter`.
2. Register via entry point `openmimicry.contracts.avatar_runtime`.
3. Ship a mock that satisfies the Protocol with zero deps.
4. Add a frontend runtime component under
   `apps/desktop/frontend/src/runtimes/<modality>/` + register in
   `runtimes/registry.ts`.
5. The `AvatarOrchestrator.swap_runtime` invariant (re-emit the
   current directive after the swap) is handled by the cognition
   layer; you don't need to touch it.

## Adding a new task runtime

1. Implement `openmimicry.core.contracts.tasks.TaskRuntimeAdapter`.
2. Declare `capabilities: set[str]` — the router uses these to
   pick the right adapter when a `TaskRequest` arrives.
3. Register via entry point `openmimicry.contracts.task_runtime`.
4. Wire it into your profile YAML under `tasks.runtimes.<name>`.

The `LocalShellAdapter` is the security-sensitive reference
implementation (allowlist-only, `shell=False`, audit log, SIGTERM →
SIGKILL cancel). Mirror its safety posture for any runtime that
touches the host filesystem.
