# OpenMimicry v1.6.1 verification

## Defect reproduced

The reported v1.6.0 request used `enabled=true` and `provider=none`.
`MemoryConfig.model_validate()` rejected it, and the uncaught validation error
escaped `POST /memory/settings` as HTTP 500.

## Automated results

- Full Python suite: **584 passed**.
- Regression cases: `On + None` and `On + Hindsight without endpoint` both
  produce HTTP 422 and do not persist settings.
- Ruff: all checks passed; 251 files formatted.
- Pyright: 0 errors, 0 warnings.
- Import-boundary checker: passed.
- Dashboard JavaScript syntax check: passed.
- Frontend: 17 test files and 92 tests passed; TypeScript typecheck and Vite
  production build passed.
- External echo TypeScript build: passed.
- Frozen pnpm lockfile installation and production dependency audit: passed;
  no known vulnerabilities reported.
- Version consistency: 27 active metadata locations checked with no mismatch.
- Configuration: the base configuration and all six profile overlays passed
  schema-v2 validation.

One upstream `StarletteDeprecationWarning` is emitted by FastAPI's TestClient
compatibility module. It is unrelated to the memory route and is not used by
the production request path.

## Manual Windows acceptance

1. Restart the backend and reload the settings page without cache.
2. Confirm the initial disabled state reads `Off + None (memory off)`.
3. Change Enabled to On; confirm Provider immediately becomes Local SQLite.
4. Save, restart the backend, and confirm the memory badge reports `local`.
5. State an explicit fact such as “My favorite color is blue.”
6. Refresh records and confirm one fact appears without duplicate raw audio or
   transcript storage.
7. Select Hindsight, clear its endpoint, and confirm the dashboard shows a
   readable validation error without an HTTP 500 traceback.

## Compatibility

- Schema version: unchanged at v2.
- SQLite schema and retention behavior: unchanged.
- Voice, STT, TTS, LLM, avatar, and character-pack behavior: unchanged.
- No secret, user overlay, database, log, environment, virtual environment,
  build output, or dependency cache belongs in the release archive.
