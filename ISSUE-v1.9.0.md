# v1.9.0 — Persistent multilingual companions, background Claude projects, and safe tools

## Problem

The v1.8 desktop can use 2D/3D avatars, saved voices, selective web research,
and Claude Code, but the settings do not yet behave as one durable companion.
Identity can be confused with a user's memory, the initial voice/avatar pair
can diverge, research behavior varies by phrasing, and project delegation lacks
live configuration and background completion UX. Multilingual interaction,
safe OS tools, per-model animation mapping, and original creator-archive import
also need a coherent implementation.

## Scope

### Identity and persistence

- [x] Rename deterministic user identity memory to `user_name` and normalize
  legacy records at prompt time.
- [x] Make personality name/aliases authoritative for assistant identity.
- [x] Rehydrate the active companion before constructing avatar and TTS
  adapters; use checked-in defaults only on first execution.
- [x] Export/import companion profile v2 with name, aliases, personality,
  voice, avatar/runtime, transform, rotation, speed, and animation aliases.
- [x] Warm voice/avatar candidates before atomically committing activation.

### Research and language

- [x] Make explicit current/internet/source questions deterministic research
  triggers in `auto` mode.
- [x] Keep sources visible only on request and remove links/citations from TTS.
- [x] Add independently selectable `auto/en/fr/es/pt` input and output.
- [x] Warm multilingual STT under a visible refresh state with rollback.

### Claude projects

- [x] Recognize direct Claude invocations reliably.
- [x] Expose CLI, auth mode, working directory, permission mode, model, and max
  turns in configuration.
- [x] Register named project roots and avoid full project rereads.
- [x] Reuse provider sessions only while a cheap Git fingerprint is unchanged.
- [x] Acknowledge immediately and run delegated work beside ordinary chat.
- [x] Persist task events/results/notifications and light the desktop bell on
  terminal updates.

### Provider-neutral tools

- [x] Add opt-in browser, Spotify search, new text file, folder, configured
  application, and alarm tools.
- [x] Enforce allowed roots, create-only files, exact app aliases, and no
  inferred shell commands.
- [x] Add a replaceable HTTP endpoint contract suitable for another desktop
  implementation or Android bridge.

### 3D and private creator assets

- [x] Persist X/Y/Z rotation and animation speed per pack.
- [x] Map eight OpenMimicry lifecycle/gesture aliases to custom embedded clips.
- [x] Import Torikinoko and MINIUS from their original creator ZIPs into a
  private local pack while preserving credits.
- [x] Do not redistribute either restricted model/archive.
- [x] Keep only `mimic_blue`, `octomimic`, and `octomimic_vrm` eligible for Git.

## Acceptance criteria

1. A saved companion restarts with the same pack, compatible runtime, voice,
   personality, name/aliases, transform, rotation, speed, and clip aliases.
2. A memory fact `user_name: Gabriel` never makes the assistant call itself
   Gabriel.
3. Explicit web questions research in `auto`; greetings do not; speech omits
   raw URLs unless the user explicitly requests spoken source detail.
4. Language changes are live, rollback-safe, and do not leave controls stuck.
5. Claude delegation returns immediately, runs in the chosen registered
   project, persists progress, and creates a visible terminal notification.
6. Tools do nothing until enabled and cannot escape roots, overwrite files, or
   execute arbitrary commands.
7. Imported VRM clip aliases control listening, thinking, speaking, emotions,
   and gestures with fallback for missing clips.
8. Creator archives import locally from originals; release ZIPs contain none of
   their copyrighted model bytes.
9. Python, frontend, lint, typecheck, build, version, and package inspections
   pass.

## Out of scope

- Bundling third-party creator models whose terms prohibit redistribution.
- Arbitrary LLM-authored shell execution.
- A native Android client; v1.9 provides the replaceable endpoint boundary.
- Provider guarantees for models that do not support web research.
