# OpenMimicry v1.6.1 — memory settings validation hotfix

## Summary

OpenMimicry v1.6.1 fixes the `POST /memory/settings` HTTP 500 observed when the
dashboard submitted `enabled=true` with `provider=none`. This is a compatible
patch over v1.6.0: configuration schema v2, memory database format, voice
runtime, character packs, and provider contracts are unchanged.

## Root cause

The dashboard exposed two independent controls and allowed the logically
invalid pair `On + None`. `MemoryConfig` correctly rejected this pair, but the
route invoked that nested validation manually and did not translate the
resulting Pydantic exception into an HTTP client error. The exception therefore
escaped as HTTP 500.

## Corrections

- Turning memory on while no provider is selected chooses **Local SQLite**, the
  private local-first default.
- Selecting **None (memory off)** turns the Enabled control off.
- The dashboard performs a final consistency check before submission.
- Hindsight cannot be enabled without an endpoint.
- The API independently enforces the same invariants and returns HTTP 422 with
  a readable, bounded error body.
- Invalid requests are never persisted.
- Pyright now includes `packages/openmimicry-memory/src`; the optional
  Hindsight import is explicitly identified as optional.

## Upgrade notes

No data migration is required. Existing SQLite memory files and retained facts
are left untouched. After merging the patch, reinstall the editable workspace
packages if your environment is not already linked to the repository, restart
the backend, open Settings, choose **On**, and save. The provider will display
**Local SQLite** unless you explicitly choose Hindsight.

Temporary v1.6.0 workaround: select **Local SQLite** before setting Enabled to
**On**.

## Verification

- 584 Python tests passed.
- Ruff lint and formatting passed for 251 files.
- Pyright passed with zero errors and zero warnings.
- Import-boundary and JavaScript syntax checks passed.
- All 92 frontend tests, TypeScript typecheck, Vite production build, frozen
  lockfile installation, and production dependency audit passed.
- The focused regression suite verifies HTTP 422 behavior and proves invalid
  settings do not call the persistence layer.
