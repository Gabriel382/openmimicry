# OpenMimicry v1.6.0 Design Appendix

**Status:** implementation candidate for collaborator review  
**Document type:** additive appendix; it does not replace the v1.0 design document  
**Configuration schema:** 2  
**Release target:** 1.6.0  
**Last updated:** 2026-07-18

## 1. Purpose

This appendix specifies the interaction, provider, personality, memory,
character-authoring, voice-provider, and distribution-profile additions made
after v1.5.1. It converts the conversational requirements that led to the
stable v1.5 voice runtime into testable component boundaries.

The governing principle is **text-path independence**: no speech recognizer,
speech synthesizer, memory provider, model catalog, or optional character tool
may prevent a typed turn from being accepted or its LLM result from entering
history. Optional work is bounded, isolated, and observable.

## 2. Scope

### 2.1 Included

- Four reply presentation modes with deterministic bubble lifetime.
- Named OpenRouter and Ollama backends, live catalog discovery, model switching,
  and session-only credentials.
- Editable personality prompt while preserving the structured avatar cue
  allow-list.
- Disabled-by-default long-term memory with local SQLite and optional Hindsight.
- Deterministic or independently configured LLM memory extraction.
- Secure character ZIP import, a simple Sprite2D creator, and a versioned
  template archive.
- Commercial/system TTS, community Piper continuity, free local Chatterbox
  cloning, and ElevenLabs BYOK.
- Schema v2, v1 migration, dependency profiles, lock material, and license
  audit tooling.

### 2.2 Excluded

- Training a new TTS foundation model.
- Automatic legal approval of imported artwork, model weights, or voices.
- Raw audio retention in memory.
- Hot-swapping STT/TTS implementations inside a running backend. Provider
  metadata can be saved in the dashboard, but an adapter change requires a
  restart.
- Full CRUD against a Hindsight bank. Those operations remain owned by the
  external Hindsight service; OpenMimicry exposes complete CRUD for local
  SQLite.

## 3. Architectural changes

### 3.1 Interaction lifecycle

Each spoken reply receives an opaque `utterance_id`. The event sequence is:

```text
LLMStarted
  -> LLMReplyComplete(speech_expected, speech_utterance_id, presentation_mode)
  -> TTSQueued(utterance_id)
  -> TTSReady(utterance_id)
  -> TTSStarted(utterance_id)
  -> exactly one of TTSFinished | TTSFailed | TTSInterrupted
```

Readiness and completion are correlated by ID. A late terminal event from an
interrupted utterance cannot release or replace the current bubble. Speaking
animation begins only at `TTSStarted`; synthesis and queueing do not imply
audible playback.

The frontend dismisses a complete reply only when both conditions hold:

1. The calculated reading deadline has elapsed.
2. The matching speech utterance is terminal, or no speech was expected.

The timer is:

```text
clamp(base_ms + character_count * ms_per_character, minimum_ms, maximum_ms)
```

### 3.2 Presentation modes

| Mode | Text publication | Speech | Failure behavior |
|---|---|---|---|
| `parallel` | Immediately after LLM completion | Queued concurrently | Text remains; failed speech releases only the audio hold |
| `voice_ready` | After matching `TTSReady` | Required when voice is enabled | Falls back to text after a bounded readiness failure |
| `text_only` | Immediately | Not queued | No audio dependency |
| `voice_only` | Hidden from avatar bubble; retained in history/accessibility surfaces | Queued | Failure notice; conversation record remains available |

`voice_ready` is bounded by `voice.tts.readiness_timeout_s`. The default is 30
seconds; the local clone profile uses 120 seconds for first-run model loading.

### 3.3 Provider switching

`LLMSwitchboard` owns named `LLMAdapter` instances. The active backend and model
are selected between turns. In-flight turns retain the adapter reference with
which they began.

Catalog discovery has only two built-in network paths:

- OpenRouter: the fixed official models endpoint, bounded to 8 MiB and 8 seconds.
- Ollama: `/api/tags` on a loopback host only. Non-loopback `api_base` values are
  rejected for discovery to avoid server-side request forgery.

Provider tokens can come from an environment-variable reference or an
in-memory session value. API responses expose booleans describing the active
credential source, never the secret.

### 3.4 Personality

The dashboard edits `system_prompt` in `config/personality.yml` through an
atomic replace. Emotion/action names, intensity bounds, and structured-output
parsing remain separate and allow-listed. A prompt cannot create a new avatar
action.

### 3.5 Memory

Memory is an optional parallel subsystem:

```text
accepted user turn
  -> deadline-bounded recall (default 150 ms)
  -> untrusted memory context appended to the main LLM input
  -> main reply completes and is published
  -> detached extraction/retention task
```

Retrieval timeout, provider error, extraction error, and write error never fail
the main turn. Failures are logged. Retrieval context is labelled untrusted to
reduce instruction-injection risk.

Providers:

- `none`: null object; zero retention and zero retrieval.
- `local`: standard-library SQLite, WAL mode, exact-fact deduplication, lexical
  retrieval, bounded result count, edit/delete/export/clear, and retention-day
  expiry.
- `hindsight`: optional official client talking to an explicitly configured
  service. OpenMimicry uses retain/recall only; service-side governance remains
  external.

Extractors:

- `deterministic`: regular expressions accept only explicit first-person name,
  location, like, dislike, and preference statements. No LLM call is made.
- `llm`: a separately selected named backend receives a strict JSON extraction
  prompt at temperature zero. Every candidate is schema-validated; invalid
  output stores nothing.

Raw audio is not part of the memory API and `store_raw_audio` is a literal
`false` schema invariant.

### 3.6 Character authoring and import

The simple creator accepts one required idle sprite and one optional speaking
sprite. It generates all lifecycle directories and validates the completed
pack before an atomic directory rename.

ZIP imports are rejected for traversal paths, absolute paths, symbolic links,
multiple manifests, excessive file count, excessive compressed or expanded
size, invalid image signatures, invalid state names, an existing pack ID, and
licenses denied by the active commercial distribution profile.

The checked-in template and `GET /pack/template` are both versioned. A new pack
ID is required for revisions; imports never overwrite an installed pack.

### 3.7 Voice providers

| Adapter | Cost path | Process boundary | Distribution profile | Notes |
|---|---|---|---|---|
| `system-command` | Free OS facility | Fixed argv subprocess | commercial | Windows System.Speech, macOS `say`, Linux `espeak-ng`; text travels through a temp file |
| `isolated-piper` | Free local | Disposable synthesis jobs | community | Current `piper-tts` code is GPL-3.0; voice model cards vary |
| `chatterbox-local` | Free local | Persistent disposable ML worker | community opt-in | MIT upstream; explicit speaker consent and local reference required |
| `elevenlabs` | Paid/BYOK | HTTPS plus OS playback | cloud opt-in | Direct HTTP; token is env/session only; voice selected in the user's account |

The Chatterbox model is loaded once at controller startup and reused. A crash,
timeout, or cancellation terminates the worker and creates a clean replacement
on the next attempt. It does not load PyTorch into the backend process.

## 4. Configuration schema v2

Schema v2 adds:

- `llm.backends`, `llm.active_backend`, and `llm.roles`.
- `interaction.response_presentation`.
- `memory`.
- `voice.tts.clone`, `secret`, `endpoint`, and `readiness_timeout_s`.
- `distribution.profile` and `reject_licenses`.

The v1→v2 migration wraps the legacy single LLM into a named backend and fills
safe defaults. Migration is deterministic and in-memory; the source YAML is not
rewritten. A future schema version remains a hard startup error.

## 5. Local API additions

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/interaction/settings` | Inspect/update presentation mode and timer |
| GET/POST | `/llm/settings` | Inspect/select named backend |
| GET | `/llm/catalog?backend=` | Discover provider models |
| POST | `/llm/model` | Select model for a named backend |
| POST | `/llm/credentials` | Set/clear session-only token |
| GET/POST | `/personality/settings` | Inspect/update system prompt |
| GET/POST | `/memory/settings` | Inspect/persist memory config; restart required |
| GET/PUT/DELETE | `/memory/records[/{id}]` | Local memory inspection and CRUD |
| POST | `/memory/clear` | Confirmed deletion of all local records |
| GET | `/memory/export` | JSON export |
| POST | `/pack/create` | Create a simple Sprite2D pack |
| GET | `/pack/template` | Download versioned template ZIP |
| POST | `/voice/clone/reference` | Store a bounded consented local reference |
| POST | `/voice/clone/remote` | Store remote voice ID/consent metadata |
| POST | `/voice/credentials` | Set/clear an in-memory ElevenLabs token |

These routes are intended for the loopback dashboard. Deployments that bind
the backend beyond loopback must add authentication and origin controls before
exposing administrative routes.

## 6. Security and privacy invariants

- Memory, cloning, cloud voice, camera, and passive listening are off by
  default unless their profiles/configuration explicitly enable them.
- Typed chat remains usable after every optional-subsystem failure.
- Tokens are never written by dashboard credential routes or returned by APIs.
- Uploaded reference recordings are capped at 20 MiB, signature-checked, given
  private file permissions, and stored outside the repository.
- Voice cloning requires a non-empty consent record. Users remain responsible
  for the speaker's rights and applicable law.
- User/LLM text is never interpolated into a shell command.
- Imported archive expansion is bounded and atomic.
- Raw microphone audio is never passed to memory.
- Commercial pack import rejects GPL, AGPL, non-commercial, research-only,
  unknown, and CC-BY-NC labels by default.

## 7. Compatibility

Python services and browser UI are OS-independent. Isolated Faster-Whisper is
supported on Windows, macOS, and Linux subject to upstream wheels and audio
drivers. System TTS uses the host facility available on each OS. Chatterbox is
source-compatible across those systems but has a large ML/hardware matrix and
requires a per-platform hardware acceptance run. Tauri bundles target Windows,
macOS, and Linux, but the Rust/Tauri suite must run in a toolchain-equipped CI
or workstation.

The existing Windows v1.5.1 Piper launcher and its preflight marker are kept
unchanged for rollback continuity.

## 8. Verification strategy

Required automated gates:

1. Full Python unit/contract/integration suite.
2. Ruff check and format check.
3. Pyright.
4. Import-boundary checker.
5. Configuration validation for every shipped profile and v1 migration.
6. Character archive adversarial tests.
7. Speech lifecycle tests for two or more utterances, stale event rejection,
   failure fallback, and bounded readiness.
8. Memory deadline, dedupe, retention, disabled-mode, and CRUD tests.
9. Frontend Vitest, TypeScript, production build, and JavaScript syntax check.
10. Frozen pnpm install and production audit.
11. Commercial dependency license audit in a clean environment.
12. Rust format/clippy/test on a host with Cargo installed.
13. Manual audio acceptance on each claimed OS/device combination.

The automated suite cannot prove microphone quality, speaker routing, cloud
account entitlement, model-weight licensing, or real-time performance on a
specific machine. Those remain release acceptance items, not inferred claims.

## 9. Rollout and rollback

Recommended branches:

```bash
git switch dev
git pull --ff-only
git switch -c task/v1.6-interaction-memory-voice
# review and test; then merge through a pull request into dev
git switch dev
git switch -c release/v1.6.0
```

Keep the v1.5.1 tag and source ZIP. Configuration files are not rewritten by
migration, so rollback consists of restoring the v1.5.1 executable/source and
selecting the prior profile. Schema-v2-only user overlay keys should be moved
aside if v1.5.1 refuses them.

## 10. Known limitations and follow-up work

- Hindsight bank CRUD is delegated to Hindsight's service UI/API.
- Chatterbox's upstream dependency closure includes a Git dependency; treat the
  profile as community/experimental until a release-lock review is completed.
- OS-native TTS voice selection is currently the host default.
- `voice_only` should not be used when captions are required for accessibility;
  the conversation dashboard remains available, but product policy may require
  forced captions.
- Administrative localhost routes do not implement authentication because the
  desktop topology is loopback-only. Remote deployment is a separate threat
  model.
- Model and asset licenses can change independently of this source release.
  Release engineering must rerun the audit and retain model cards/notices.

## 11. Acceptance criteria

The appendix is accepted when:

- all automated gates that can run in the release environment pass;
- unavailable gates are explicitly named in the release notes;
- a collaborator can select OpenRouter or Ollama and a model without editing
  secrets into YAML;
- presentation behavior matches the table in §3.2 for two sequential replies;
- enabling memory is an explicit persisted action and disabling it yields no
  retrieval or retention;
- local memory can be inspected, edited, exported, deleted, and expired;
- a character can be created or imported without overwriting an existing pack;
- commercial installation excludes Piper and Chatterbox;
- local cloning cannot start without a reference and consent record;
- optional voice failure leaves typed chat and reply history operational.
