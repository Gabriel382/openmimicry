# OpenMimicry v1.8.0 — Integrated Runtime Architecture Appendix

Status: collaborator review  
Scope: additive appendix; it does not replace the frozen v1 design or v1.6 appendix.

## 1. Purpose

Version 1.8 turns the desktop companion into a stable foreground surface over
replaceable cognition, memory, tool, voice, and task providers. The release
adds three connected capabilities:

1. a production Three.js path for VRM, VRMA, glTF, embedded animation clips,
   expressions, gaze hooks, transparent rendering, and configurable speed;
2. local task agents, especially a user-authenticated Claude CLI and the
   optional PicoClaw executable, associated with explicit project roots;
3. durable task/project/event/notification state that remains inspectable
   after the backend or desktop closes.

The architecture continues to forbid provider-specific imports outside the
assembly boundary. Optional executables and services are adapters, not hidden
requirements.

## 2. Layer boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| Desktop surface | transparent overlay, controls, composer, dashboard link | model credentials or task execution |
| Backend orchestration | turn lease, adapter wiring, health, hot refresh | provider business logic |
| Cognition | LLM generation and optional server-side web research | avatar files, task persistence |
| Task runtime | Claude CLI, PicoClaw, MCP, shell policies | conversation rendering |
| Durable journal | projects, task lifecycle, events, notifications | provider secrets or raw audio |
| Avatar runtime | Sprite2D or Three.js projection/rendering | conversation or memory policy |
| Memory | optional retrieval and post-reply observation | raw microphone data |

## 3. Durable tasks and projects

`JournaledTaskRuntime` wraps the frozen `TaskRuntimeAdapter`. It is the only
consumer of downstream update streams and re-broadcasts updates to callers
while recording them in SQLite. This prevents two consumers from racing over a
single provider stream.

SQLite contains:

- `projects`: stable id, display name, absolute root, description, preferred
  runtime;
- `tasks`: request, runtime, project, provider session id, status, progress,
  result, timestamps;
- `task_events`: append-only contract-shaped updates;
- `notifications`: terminal results shown separately from conversation.

On startup, unfinished rows become `interrupted`; they never remain falsely
`running`. Provider sessions may be resumed only when the adapter and user
explicitly support it. No API key, environment dump, raw audio, or model cache
is written to this database.

## 4. Claude CLI and PicoClaw

Claude runs in non-interactive print mode with stream JSON. The default
`auth_mode: subscription` intentionally omits `ANTHROPIC_API_KEY`, allowing the
installed Claude CLI to use the user's existing local Claude authentication.
`auth_mode: api` is an explicit alternative. Only a curated environment is
forwarded.

Each task receives a project working directory. A returned Claude session id is
stored as provider metadata and can be supplied as `provider_session_id` on a
later task. Permission policy remains Claude CLI configuration owned by the
user; OpenMimicry does not add a permission-bypass flag.

PicoClaw runs its documented one-shot form:

```text
picoclaw agent -m "<instructions>"
```

It is optional and health reports unavailable when the executable is absent.
PicoClaw configuration, providers, MCP servers, and secrets remain in
PicoClaw's own security configuration.

## 5. Web and tools

Web access is a backend capability, not a property of the avatar. Each named
LLM backend has an independent mode:

- `off`: never attach the provider web plugin;
- `auto`: attach it only to explicit or time-sensitive research questions;
- `always`: attach it to every turn.

The automatic gate is deterministic. Greetings and simple companion questions
do not invoke web research. Current weather, prices, schedules, news, explicit
search requests, and similar phrases do. The v1.8 implementation uses
OpenRouter's `web` server plugin only when selected; a future search adapter can
replace this without changing the conversation contract.

External actions belong to task/tool adapters. The built-in layer offers
MCP-agent, PicoClaw, Claude CLI, and allowlisted local shell adapters. Users may
replace the whole task backend through configuration.

## 6. Three.js and VRM

The Three.js runtime owns a transparent, antialiased WebGL renderer and a
request-animation-frame loop. It loads VRM or glTF/GLB, plays embedded clips
through `AnimationMixer`, cross-fades transitions, updates VRM expressions, and
advances VRM spring/update state each frame.

VRMA files are loaded through `@pixiv/three-vrm-animation`. The pack runtime
configuration maps stable semantic names to asset URLs:

```yaml
avatar:
  runtime: threejs
  pack: my_vrm
  animation_speed: 1.0
  runtimes:
    threejs:
      pack_path: ~/.openmimicry/characters/my_vrm
      animations:
        idle: /static/characters/my_vrm/idle.vrma
        wave: /static/characters/my_vrm/wave.vrma
```

Animation speed is bounded to `0.1..4.0`. Unsupported expressions or clips
degrade to the existing fallback chain. A failed 3D load produces an explicit
runtime error without taking down text chat.

## 7. Hot refresh and health

Voice-profile activation warms a replacement TTS adapter before swapping it
into `SpeechController`; the previous adapter closes only after the new one is
ready. STT, WebSockets, conversation state, and task execution remain alive.

Memory changes build a replacement service while the supervisor blocks new
turns. Controls should be disabled while runtime state is `refreshing`. A
current conversation turn must finish before memory refresh is admitted.

Health is split into liveness, readiness, and component probes. Readiness means
the runtime is ready, no conversation lease is active, and the selected LLM is
healthy. Optional providers may be degraded without making text-only
conversation unavailable.

## 8. Localization

The configuration recognizes `en`, `fr`, `es`, and `pt` UI locales. STT
language remains independently configurable. Provider and voice availability
varies by language; selection failure must remain visible and must preserve the
text path.

## 9. Privacy, licensing, and portability

Only `mimic_blue`, `octomimic`, and `octomimic_vrm` are eligible for source
control under `characters/`. Other local characters, voice references,
personalities, exported companion bundles, logs, memory, and task databases
remain private by default.

OpenMimicry code is MIT. Optional providers, models, voices, and user-imported
assets retain their own terms. Exporting a companion bundle never exports API
keys, memory, history, logs, or caches; biometric reference audio requires an
explicit confirmation.

## 10. Acceptance invariants

- Conversation output never waits for or disappears because an optional tool
  adapter is missing.
- Only one foreground conversation turn is submitted at a time.
- Background tasks may continue and report completion through notifications.
- Task status survives process restart and stale live states become
  `interrupted`.
- Claude subscription mode works without an Anthropic API key.
- Automatic web mode does not activate for greetings.
- Voice or memory changes expose `refreshing` and do not require a process
  restart.
- The Three.js canvas is transparent and disposes GPU/animation resources.
- User-created companion assets remain ignored by Git.

