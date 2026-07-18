# v1.4.0 — deterministic voice turns, model switching, and character import

## Problem

Windows voice sessions can emit duplicate or overlapping STT finals, causing
assistant responses to appear out of order. RealtimeTTS may speak only its
first response, wake names such as Mimi are poorly recognized, PTT pays model
startup latency, and collaborators cannot see/switch the active model or
install a character through the dashboard.

## Scope

- Serialize accepted text, PTT, and wake turns.
- Retain only 3–5 successful exchanges as LLM context (implementation: 4).
- Display all final voice transcripts; mark wake-name-missing/duplicate turns
  and exclude them from model context.
- Prewarm configurable RealtimeSTT quality and bias it with wake names/aliases.
- Reuse a Windows-safe TTS engine and synchronize text with playback start.
- Expose configured OpenRouter/Ollama profiles and exact model identity.
- Import a validated Sprite2D character ZIP from the local dashboard.

## Acceptance criteria

- [x] Older replies cannot overtake newer accepted questions.
- [x] Only successful completed pairs enter bounded context.
- [x] `Me me` can be configured as an alias for `Mimi`.
- [x] Identical wake finals inside 2.5 seconds are visible but not resubmitted.
- [x] `small.en` is the default; tiny/base/small are selectable and prewarmed.
- [x] PTT release requests immediate finalization.
- [x] Every sequential reply uses the same serialized TTS engine and is heard.
- [x] Visible reply begins only after audio start or an explicit TTS fallback.
- [x] Dashboard identifies/switches OpenRouter and Ollama for the next turn.
- [x] Character ZIP import rejects traversal, symlinks, bombs, invalid packs,
  and existing IDs without overwriting data.
- [x] Python/frontend tests, builds, lint, static typing, and validators pass.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only origin dev
git switch -c feat/v1.4-interaction-pipeline

# commit and push the implementation
git add -A
git commit -m "feat: stabilize multimodal interactions and add runtime imports"
git push -u origin feat/v1.4-interaction-pipeline
```

Open a pull request from `feat/v1.4-interaction-pipeline` into `dev`. After
review and CI:

```bash
git switch dev
git pull --ff-only origin dev
git merge --ff-only feat/v1.4-interaction-pipeline
git push origin dev
```

Promote `dev` through the repository's normal release PR, then tag the merged
release commit:

```bash
git tag -a v1.4.0 -m "OpenMimicry v1.4.0"
git push origin v1.4.0
```

Versioning rationale: this is a minor release because it adds backward-
compatible configuration/API/UI capabilities; it is not only a patch fix.
