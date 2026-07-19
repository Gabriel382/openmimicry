# Optional long-term memory

Long-term memory is disabled by default. It is deliberately separate from the
short conversation window (`llm.history_turns`), which remains four completed
exchanges by default.

## Processing model

For an accepted turn, OpenMimicry performs a deadline-bounded recall in
parallel with normal setup, labels recalled facts as untrusted context, and
then asks the main LLM for a reply. After the visible reply is complete, a
detached task extracts and stores new candidates. Recall, extraction, and
storage failures are logged but cannot fail typed chat.

Memory extraction is not taken from an unconstrained `memory` key in the main
LLM response. That would couple visible reply success to retention correctness
and give one prompt too many responsibilities. Instead, choose one of:

- `deterministic`: no memory LLM. It stores only explicit first-person name,
  location, like, dislike, and preference statements.
- `llm`: a separately chosen named backend runs a strict JSON extraction at
  temperature zero. Invalid output stores nothing.

The memory backend/model may therefore be different from the conversation
backend/model and never delays reply publication beyond the recall deadline.

## Local SQLite

Choose `local` for the default private, deterministic provider. It uses a
user-data SQLite database, WAL mode, exact-fact deduplication, lexical recall,
and retention expiry. The dashboard exposes list, edit, delete, clear, and JSON
export operations.

Example user overlay:

```yaml
memory:
  enabled: true
  provider: local
  database_path: ~/.openmimicry/memory/memory.sqlite3
  extraction_mode: deterministic
  retrieval_limit: 6
  retrieval_deadline_ms: 150
  retention_days: 365
  store_raw_audio: false
```

`store_raw_audio` is a schema invariant and must remain `false`. Heard
transcript diagnostics and long-term memory are separate data sets.

## Independent LLM extraction

Set `extraction_mode: llm` and choose `llm_backend` from the same named backend
registry used for conversation. The selected backend can point to OpenRouter,
Ollama, or another configured LiteLLM provider. Credentials keep their normal
environment/session-only behavior.

```yaml
memory:
  enabled: true
  provider: local
  extraction_mode: llm
  llm_backend: ollama
  retrieval_deadline_ms: 150
  retention_days: 365
  store_raw_audio: false
```

## Hindsight

Install the optional client with the Hindsight requirements profile and select
`provider: hindsight` plus an explicit endpoint. OpenMimicry performs
retain/recall through the provider; bank administration and full CRUD remain
owned by Hindsight. Local `/memory/records` CRUD is not a surrogate for a
remote bank.

## Privacy and deletion

- Enable memory only after telling the person using the assistant what will be
  retained.
- Prefer deterministic extraction when predictability is more important than
  coverage.
- Use the shortest useful retention period.
- Export before destructive changes, and require the dashboard confirmation
  before clearing local memory.
- Treat recalled text as untrusted. It may contain stale or adversarial user
  statements and must never override system/tool policy.

