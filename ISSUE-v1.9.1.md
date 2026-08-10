# v1.9.1: stabilize identity, multilingual voice, companions, VRM, tools, and Claude

## Problem

v1.9.0 exposed conflicting assistant identity fields, opaque language refresh,
inconsistent companion voice selection, incomplete VRM controls, silent tool
fallthrough, and position-sensitive Claude intent recognition.

## Acceptance criteria

- [x] Personality name/aliases are the sole live assistant identity source.
- [x] Voice no longer exposes duplicate wake identity controls.
- [x] Language changes return immediately and expose preparation status.
- [x] Brazilian Portuguese uses `pt-BR` and a matching standard Piper voice.
- [x] Failed language preparation leaves the old voice/STT active.
- [x] Companion activation applies avatar, runtime, transform, identity,
  personality, and bundled voice consistently at runtime and startup.
- [x] Active voice selector reflects the voice actually in use.
- [x] Private companions and characters can be exported and removed; bundled
  defaults cannot be removed.
- [x] Three.js accepts full rotation and legacy creator imports face forward.
- [x] Embedded VRM clips can be discovered, selected, and auto-mapped.
- [x] Missing embedded animations are reported explicitly.
- [x] `Set an alarm to 17h!` schedules the built-in durable alarm.
- [x] Tool policy/routing/scheduling/fallthrough is logged.
- [x] `ask claude` is recognized anywhere in an accepted wake/PTT/text turn.
- [x] Claude acknowledgements keep thinking until audio is ready, then reveal
  text and play voice together.
- [x] Default Claude directory resolves to the current project root on first use.
- [x] Python, frontend, static, version, and packaging verification passes.

## Out of scope

- Fabricating animation clips for VRMs that do not contain them.
- Redistributing restricted creator avatars.
- Forcing a custom cloned voice to support languages its provider cannot speak.
- Mutating the operating system's native Clock application.
