# v1.6.0 — interaction configuration, provider switching, optional memory, character authoring, and voice providers

## Goal

Ship the post-v1.5.1 interaction improvements without regressing the stable
multi-turn text/voice lifecycle. Optional speech, memory, catalogs, cloning,
and character tools must remain bounded and must never block typed chat.

## Scope

- Correlate TTS lifecycle events by utterance ID and add `parallel`,
  `voice_ready`, `text_only`, and `voice_only` presentation modes.
- Keep reply text until both its character-based reading timer and matching
  speech terminal event complete.
- Add named OpenRouter/Ollama backends, bounded catalog discovery, model
  selection, and environment/session-only credentials. Default OpenRouter to
  `openrouter/openai/gpt-oss-20b`.
- Add an editable personality prompt without weakening structured avatar cue
  validation.
- Add disabled-by-default memory: deterministic local SQLite, independent-LLM
  extraction, and optional Hindsight; include local inspect/edit/export/delete.
- Add secure Sprite2D ZIP import, a simple character creator, and a versioned
  example archive.
- Add OS-native commercial-default TTS, opt-in local Chatterbox cloning, and
  ElevenLabs BYOK while preserving the community Piper rollback path.
- Add schema v2 migration, profile-specific dependency inputs/lock, license
  audit tooling, documentation, acceptance guide, and versioned release ZIP.

## Non-negotiable invariants

- Accepted text appears in history before optional processing.
- A failed/hung TTS, STT, memory, catalog, or clone worker cannot wedge the
  conversation queue or avatar state.
- A stale TTS event cannot control the current reply.
- Memory and raw-audio retention are off by default; raw audio cannot be stored
  by the memory schema.
- API keys are never returned or persisted by dashboard credential routes.
- Archive extraction is bounded, traversal-safe, non-overwriting, and atomic.
- Commercial installs exclude Piper and Chatterbox and pass a fail-closed
  installed-dependency license audit.

## Acceptance criteria

- Full Python/frontend/config/import suites pass.
- Strict commercial dependency audit reports no denied/missing packages.
- Two sequential text/PTT/wake turns recover after interrupt/failure.
- All presentation modes match the v1.6 design appendix.
- Memory disabled mode performs no retention; local memory CRUD/expiry works.
- Valid pack create/import works; adversarial archives leave no partial pack.
- Clone configuration requires consent and leaves tokens out of YAML.
- Per-platform audio and Rust/Tauri checks are recorded rather than inferred.

## Suggested branches and versioning

```bash
git switch dev
git pull --ff-only
git switch -c task/v1.6-interaction-memory-voice
# commit implementation and open PR into dev
git switch dev
git pull --ff-only
git switch -c release/v1.6.0
# apply release metadata, final QA, then PR/tag v1.6.0
```

Version all project packages/apps as `1.6.0`. Name downloadable archives with
the version, for example `OpenMimicry-v1.6.0-source.zip` and
`OpenMimicry-character-template-v1.6.0.zip`.

