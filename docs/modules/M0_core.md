# Module M0: `openmimicry-core`

## Goal (1 line)

Implement the concrete runtime services that every other module depends on: the `EventBus`, the `AppConfig` loader with hot-reload, the `RuntimeStore`, structured logging, and lifecycle hooks — all behind the Protocols and schemas already frozen in Phase 0.

## Scope and non-scope

**In scope.**

- `EventBus` concrete implementation (publish + multi-subscriber fan-out via per-subscriber `asyncio.Queue`).
- Configuration loader: YAML reading, env-var overlay, profile merging, Pydantic validation, schema-versioning.
- `RuntimeStore`: small immutable snapshot of "what's currently true" — current `AvatarDirective`, current speech state, last LLM reply, etc. Read-only outside the runtime; mutated only via bus subscribers internal to M0.
- Structured logging via `structlog` with a bus-tap subscriber that logs every `RuntimeEvent` at DEBUG plus notable ones at INFO.
- Hot-reload of safe config sections, driven by `watchfiles`.
- Lifecycle helpers: `Runtime.start()`, `Runtime.stop()`, an `async with` context manager.

**Non-scope.**

- The schemas and Protocols themselves (Phase 0 owns).
- Any adapter implementation (M1–M5 own).
- The HTTP/WebSocket transport (M6 owns).
- The frontend or Tauri (M7, M8 own).

## Inputs (immutable, from contracts.md)

From `openmimicry.core.contracts` (its own package — but the Protocol and schema definitions are still treated as inputs you must satisfy):

- `EventBus` class signature from `contracts.md` §2.2.
- `RuntimeEvent` discriminated union from `contracts.md` §2.1.
- `AppConfig` and every sub-config from `contracts.md` §7 / [`../configuration.md`](../configuration.md).
- `AvatarDirective` from `contracts.md` §2.3 (read-only; M0 stores the latest in `RuntimeStore`).

Imports allowed from outside: `pydantic`, `pyyaml`, `structlog`, `watchfiles`, `anyio` or `asyncio`. Nothing from sibling `openmimicry-*` packages.

## Outputs (this module owns)

```text
packages/openmimicry-core/src/openmimicry/core/
  bus.py                  # concrete EventBus implementation
  runtime.py              # Runtime class: start/stop, holds bus + config + store
  store.py                # RuntimeStore (immutable snapshots with .update(...))
  config/
    __init__.py
    loader.py             # load(path) -> AppConfig with env + profile merge
    reloader.py           # watchfiles-driven hot reload
    migrations.py         # schema_version migrations (v1 only for now)
  logging/
    __init__.py
    setup.py              # structlog config
    bus_tap.py            # subscribes to EventBus, logs each event
  lifecycle.py            # context managers, signal handlers
```

Plus tests:

```text
tests/unit/core/
  test_bus.py
  test_runtime.py
  test_store.py
  test_config_loader.py
  test_config_reloader.py
  test_logging.py
```

## Mock implementations this module provides

M0 ships concrete implementations, not mocks. However:

- A `tests/conftest.py` fixture `event_bus()` yielding a fresh `EventBus` per test.
- A `tests/conftest.py` fixture `app_config(tmp_path, ...)` that writes a minimal valid YAML and returns the parsed `AppConfig`.
- A `tests/fixtures/configs/minimal.yaml` reference config used across the workspace.

## Test surface

- **Unit.** Bus publish/subscribe ordering; multiple subscribers each get all events; `aclose()` drains and shuts down; backpressure when a subscriber stalls (use bounded queues with `maxsize` per subscriber and document drop policy).
- **Unit.** Config loader: default fallback when no file exists; env override applied last; profile merge layered between file and env; `schema_version` mismatch errors with helpful message; migration v1 → v1 is a no-op; invalid YAML produces a structured error pointing at the path.
- **Unit.** Reloader: on file change, re-merges and republishes `ConfigUpdated(diff)`. Diff contains only changed leaves.
- **Unit.** Store: `update(event: RuntimeEvent)` returns a new snapshot; previous snapshots are unaffected (immutability).
- **Unit.** Logging: an `ErrorEvent` produces an INFO line; a `TTSChunkSpoken` produces a DEBUG line; log records are valid JSON when `log_format=json`.
- **Integration.** Wire `Runtime.start()`, publish a few events, assert the store updates and logs appear.

## Step-by-step plan (atomic, numbered)

1. Implement `bus.py`. `EventBus.publish(event)` is synchronous; it writes to every subscriber's `asyncio.Queue`. `subscribe()` returns an async iterator. `aclose()` closes all subscribers. Use `maxsize=1024` per subscriber; drop oldest with a `Warning` log if a subscriber falls behind by more than the queue length (document this in the docstring).
2. Implement `store.py`. `RuntimeStore` holds: `current_directive: AvatarDirective | None`, `last_user_text: str | None`, `last_assistant_text: str | None`, `is_speaking: bool`, `live_wake_enabled: bool`, `active_tasks: dict[str, TaskUpdate]`. Provide `update(event)` that returns a new store (use `pydantic.BaseModel` with `model_copy(update={...})`).
3. Implement `config/loader.py::load(path: Path | None = None) -> AppConfig`. Apply the resolution order from `configuration.md` §1. Use `os.path.expanduser` for `~`. Convert `OPENMIMICRY__SECTION__KEY` env vars to nested dict updates. Validate with `AppConfig.model_validate`. On `schema_version` mismatch, call into `migrations`.
4. Implement `config/migrations.py`. Empty for v1. Define the signature `def migrate(data: dict, from_version: int, to_version: int) -> dict` and a registry pattern so v2 can be added without touching v1.
5. Implement `config/reloader.py`. Use `watchfiles.awatch`. On a change, re-run the loader, compute a structured diff (use `deepdiff` or write a tiny recursive walker), publish `ConfigUpdated(diff=...)` on the bus. Reloader is opt-in: `Runtime` instantiates it only if `app.config_watch=true`.
6. Implement `logging/setup.py`. Configure structlog with a JSON renderer when `app.log_format=json`, a console renderer otherwise. Bind `app_version`, `pid`.
7. Implement `logging/bus_tap.py`. A coroutine that subscribes to the bus and logs each event with appropriate level. `ErrorEvent` → ERROR; `TaskSubmitted`, `TaskCompleted`, `WakeDetected`, `LLMReplyComplete`, `TTSInterrupted`, `ConfigUpdated` → INFO; everything else → DEBUG.
8. Implement `runtime.py::Runtime`. Holds: `bus`, `config`, `store`, `_subscribers: list[asyncio.Task]`. `async def start()` starts the bus tap and (optionally) the config reloader as background tasks, and a store-updater subscriber. `async def stop()` cancels them and `await bus.aclose()`. Implement `__aenter__`/`__aexit__`.
9. Implement `lifecycle.py`. Provide `install_signal_handlers(runtime)` so SIGINT/SIGTERM call `runtime.stop()`.
10. Write the unit tests listed in "Test surface". Coverage gate for M0: ≥ 90%.
11. Add a one-page README at `packages/openmimicry-core/README.md` summarising usage with a code example: `async with Runtime(config=AppConfig(...)) as rt: ...`.
12. Update workspace `CHANGELOG.md` under `## Unreleased`.
13. Run `make ci`. Open PR `feat(core): M0 — EventBus, Runtime, config loader, store, logging`.

## Definition of done (checklist)

- [ ] Every file in "Outputs" exists and is type-checked.
- [ ] Unit tests pass with ≥ 90% coverage on M0 source.
- [ ] `EventBus` correctly fans out to multiple subscribers with the documented drop policy.
- [ ] `AppConfig` loads from YAML, accepts env overrides via `OPENMIMICRY__...`, accepts a `OPENMIMICRY_PROFILE` overlay.
- [ ] `ConfigUpdated` is published when the YAML file is edited (verified by an integration test using a temp file).
- [ ] `RuntimeStore` is immutable; mutation attempts raise.
- [ ] `Runtime` works as an `async with` context manager.
- [ ] `scripts/check_imports.py` is clean (no sibling-package imports).
- [ ] `CHANGELOG.md` has the M0 entry.
- [ ] `make ci` green on Ubuntu + Windows.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M0 (`openmimicry-core`)** of OpenMimicry. Phase 0 has already landed — the Protocols and schemas exist as code under `packages/openmimicry-core/src/openmimicry/core/contracts/` and `.../schemas/`. Your job is to add the **concrete runtime services** behind those signatures.
>
> Read these files first, in order:
>
> 1. `docs/contracts.md` §2 and §7 — the frozen interfaces you must satisfy.
> 2. `docs/modules/M0_core.md` — this brief.
> 3. `docs/configuration.md` — the YAML schema and resolution order.
> 4. `docs/architecture.md` §7 and §14 — bus and lifecycle context.
>
> Implement the 13-step plan. Use `pydantic` v2, `pyyaml`, `structlog`, `watchfiles`, and stdlib `asyncio`. No other dependencies.
>
> Constraints: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, or `openmimicry-tasks`. The CI step `scripts/check_imports.py` will reject the PR otherwise. Do not edit anything under `packages/openmimicry-core/src/openmimicry/core/contracts/` or `.../schemas/` — those are frozen. If you find a gap there, stop and ask.
>
> Open the PR titled `feat(core): M0 — EventBus, Runtime, config loader, store, logging` with every Definition-of-done item ticked.
