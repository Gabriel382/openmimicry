# OpenMimicry v1.6.0 release notes

OpenMimicry v1.6.0 makes interaction presentation, LLM/model choice,
personality, optional memory, character authoring, and voice providers
configurable while preserving the v1.5.1 isolated multi-turn voice foundation.

## Highlights

- Four deterministic reply modes and utterance-correlated TTS lifecycle.
- OpenRouter/Ollama catalogs, named backend roles, hot model switching, and
  session-only credentials.
- Editable personality prompt with the avatar cue allow-list kept separate.
- Optional local SQLite or Hindsight memory, deterministic or independent-LLM
  extraction, strict deadlines, retention, and local CRUD/export.
- Simple Sprite2D creator plus hardened, license-aware ZIP import.
- Commercial OS-native TTS, free local consent-gated Chatterbox cloning,
  ElevenLabs BYOK, and isolated community Piper continuity.
- Schema v2 migration, commercial dependency lock/audit, third-party notices,
  design appendix, and an operational acceptance guide.

## Compatibility and migration

Schema-v1 configuration is migrated in memory to safe v2 defaults; source YAML
is not rewritten. Changing an STT/TTS adapter or memory provider requires a
backend restart. The v1.5.1 Windows Piper launcher remains unchanged for
rollback continuity.

## Distribution note

The source is MIT. Optional dependencies, cloud services, model weights, voice
files, recordings, and character assets retain their own terms. Use the
commercial profile/lock for the conservative path and review
`docs/licensing.md` before distribution.

## Verification record

The release workspace passed 581 Python tests, 92 frontend tests, Ruff,
Pyright, import/version/config/pack validation, frozen frontend install,
TypeScript and production builds, hash-required commercial lock validation,
the strict commercial license audit, and a production pnpm audit with no known
vulnerabilities. See `OpenMimicry-v1.6.0-Verification.md` for the exact record.

Cargo/Tauri, real audio hardware, cloud accounts, local clone inference, and
Windows/macOS matrices were unavailable and are explicitly **not run**, not
inferred as passing. Complete `docs/V1.6.0_ACCEPTANCE.md` on those targets
before claiming them as release-verified.
