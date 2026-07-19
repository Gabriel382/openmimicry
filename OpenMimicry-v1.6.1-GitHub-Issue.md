# Fix memory settings validation and `On + None` dashboard state

## Version

Target: `v1.6.1`

## Branch workflow

```bash
git switch dev
git pull --ff-only
git switch -c task/v1.6.1-memory-settings-validation
```

After implementation and review, open a pull request into `dev`. For release:

```bash
git switch dev
git pull --ff-only
git switch -c release/v1.6.1
# Run final acceptance checks, merge, then tag v1.6.1.
```

## Problem

The v1.6.0 dashboard permits long-term memory to be enabled while the provider
remains `None`. The core schema rejects that combination, but
`POST /memory/settings` does not catch the nested Pydantic validation error, so
the user receives HTTP 500 and the backend prints a traceback.

## Required behavior

- The dashboard must not retain or submit `enabled=true, provider=none`.
- Enabling memory from its default state must select Local SQLite.
- Selecting the `none` provider must turn memory off.
- Enabling Hindsight without an endpoint must fail before persistence.
- Direct or stale clients must receive HTTP 422, never HTTP 500.
- Invalid settings must never be written to the user overlay.
- Raw audio must remain impossible to store.

## Acceptance criteria

- [ ] From the default `Off + None` state, selecting `On` changes the provider
      to `Local SQLite`.
- [ ] Selecting `None (memory off)` changes Enabled to `Off`.
- [ ] Saving `On + Local SQLite` succeeds and reports that restart is required.
- [ ] Saving `On + Hindsight` without an endpoint presents a readable error.
- [ ] A direct request containing `enabled=true, provider=none` returns 422.
- [ ] Rejected requests make zero calls to `persist_memory_settings`.
- [ ] Existing SQLite facts survive upgrade and backend restart.
- [ ] Full Python, Ruff, Pyright, import-boundary, and frontend checks pass.

## Regression test payload

```json
{
  "enabled": true,
  "provider": "none",
  "database_path": "~/.openmimicry/memory/memory.sqlite3",
  "endpoint": null,
  "retrieval_limit": 6,
  "retrieval_deadline_ms": 150,
  "retention_days": 365,
  "extraction_mode": "deterministic",
  "llm_backend": null
}
```

Expected: HTTP 422 with a message instructing the user to select Local SQLite
or Hindsight. No settings file mutation.

