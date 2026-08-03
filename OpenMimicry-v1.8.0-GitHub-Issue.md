# v1.8.0 — Integrated 3D, local agents, providers, and durable tasks

## Goal

Ship the next integrated OpenMimicry increment across quality of life, 3D
avatars, and replaceable provider interactions without weakening the frozen
adapter boundaries or privacy defaults.

## User outcomes

- Import and run VRM/glTF/GLB characters with embedded animation clips and
  optional VRMA files in the transparent desktop overlay.
- Change overall animation speed from configuration.
- Use the locally installed/authenticated Claude CLI through a Claude
  subscription; retain Anthropic API mode as an option.
- Run PicoClaw as an optional task backend.
- Associate tasks with named project folders, run them in the background, and
  inspect progress after reopening OpenMimicry.
- Receive task-completion notifications without interrupting conversation.
- Select OpenRouter or Ollama models and configure web research per backend.
- Avoid web calls for greetings when automatic research is selected.
- Hot-activate a saved voice profile or memory provider while the UI visibly
  blocks incompatible actions during refresh.
- Retain the last selected pack, runtime, and voice profile.
- Keep all locally created avatar, personality, and voice assets out of Git,
  except the three redistributable default packs.

## Implementation

- [x] Add `JournaledTaskRuntime` and SQLite projects/tasks/events/notifications.
- [x] Mark unfinished task rows interrupted on startup.
- [x] Expose task/project/notification HTTP routes and dashboard history.
- [x] Correct `TaskRouter.submit` to use capability selection.
- [x] Add Claude stream-JSON, subscription/API modes, project CWD, and session
  metadata.
- [x] Replace PicoClaw stub with optional executable adapter.
- [x] Add per-backend web modes `off|auto|always` and a deterministic automatic
  research gate.
- [x] Add transparent Three.js renderer loop, `AnimationMixer` cross-fades,
  VRM update, VRMA loading, and animation speed.
- [x] Validate 3D character archives without requiring Sprite2D emotions.
- [x] Add hot TTS and memory replacement with supervisor `refreshing` state.
- [x] Persist pack/runtime/voice-profile selectors.
- [x] Remove the unnecessary frontend router dependency.
- [x] Add the integrated profile and cross-platform install paths.
- [x] Add architecture, migration, operations, and acceptance documentation.

## Acceptance

- [x] Python suite passes (one hardware/NumPy-dependent Chatterbox test may skip
  in a minimal CI environment).
- [x] Frontend Vitest suite and TypeScript typecheck pass.
- [x] Production dependency audit reports no known vulnerabilities.
- [x] Import-boundary and version-consistency checks pass.
- [ ] Native Tauri build/test runs on a machine with Rust/Cargo and OS GUI
  prerequisites.
- [ ] VRM/VRMA and local Claude/Pico smoke tests run on target hardware with
  user-supplied assets and installed CLIs.

## Out of scope

- Bundling Claude Code, PicoClaw, proprietary models, provider credentials, or
  user-created companion assets.
- Silently enabling web access or OS actions.
- Persisting raw audio.
- Treating a provider session as a substitute for explicit project selection.

