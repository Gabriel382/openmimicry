# feat(core): Phase 0 contract freeze + M0 runtime

Implements **Phase 0 (contract freeze)** and **M0 (`openmimicry-core` runtime)** per the briefs in `docs/modules/M_phase0_contract_freeze.md` and `docs/modules/M0_core.md`. `docs/contracts.md` is the source of truth; this PR translates it to runnable Python and adds the M0 runtime services behind those signatures.

## What lands

### Phase 0 — Contract freeze

- `packages/openmimicry-core/` workspace package with `pyproject.toml`.
- `openmimicry.core.schemas.*` — every frozen Pydantic v2 model from `contracts.md` §2–§7:
  - `events.py`: 17 event variants + a `RuntimeEvent = Annotated[Union[...], Field(discriminator="kind")]` union and a pre-built `RuntimeEventAdapter: TypeAdapter`.
  - `llm.py`, `voice.py`, `tasks.py`, `avatar.py`, `app.py` (AppConfig + every typed sub-config).
- `openmimicry.core.contracts.*` — every `@runtime_checkable` Protocol:
  - `LLMAdapter`, `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController`, `TaskRuntimeAdapter`, `AvatarRuntimeAdapter`, `AvatarDirector`, `AvatarOrchestrator`.
  - `EventBus` signature class (concrete impl ships in this same PR under M0).
- Sibling packages `openmimicry-{llm,voice,avatar,tasks}` with their own `pyproject.toml` declaring a path dep on `openmimicry-core`, plus stub `mocks.py` that raises `NotImplementedError("delivered by Mx; see docs/modules/...")`. M1–M5 replace those stubs wholesale.
- `tests/contract/` with `conftest.py` that loads entry points from `openmimicry.contracts.<protocol_name>` and parametrises every per-protocol test. Test bodies `pytest.skip("awaiting Mx")` until adapters land.
- `tests/unit/core/test_schemas.py` — round-trip every event variant through JSON, assert `frozen=True` enforcement, assert `RuntimeEvent` discriminated parsing.
- `tests/unit/core/test_imports.py` — runs `scripts/check_imports.py` and asserts an ergonomic `from openmimicry.core import LLMAdapter, AppConfig, EventBus, ...` succeeds.

### M0 — `openmimicry-core` runtime services

- `bus.py`: concrete `EventBus` with one bounded `asyncio.Queue` per subscriber (default `maxsize=1024`). Publish is sync; subscribe is sync and returns an async iterator (registration happens at call time, not at first iteration, so publish-before-iterate is delivered). Drop policy: drop oldest + single warning per subscriber.
- `store.py`: immutable `RuntimeStore` (Pydantic frozen) with `.update(event)` that returns a new snapshot and `.with_directive(d)` for the director's path. Covers `UserTextSubmitted`, `UserSpeechFinal` (normal), `LLMReplyComplete`, `TTSStarted/Finished/Interrupted`, `WakeDetected`, `TaskSubmitted/Updated/Completed`, `ConfigUpdated` (live-wake toggle from diff).
- `config/loader.py`: YAML reading + deep merge + profile overlay (`OPENMIMICRY_PROFILE` -> `config/profiles/<name>.yaml`) + env override (`OPENMIMICRY__SECTION__KEY`, with boolean/JSON/number coercion). Pydantic validation surfaces as `ConfigError(where=...)`. Future `schema_version` raises; older requires `allow_migrate=True`.
- `config/migrations.py`: registry pattern (`@register_migration(from_version=N, to_version=N+1)`) walked by `migrate(data, from_version, to_version)`. Empty for v1 today; v2 plugs in without touching v1.
- `config/reloader.py`: `watchfiles.awatch` loop; on change re-loads, computes a structured leaf-diff (`diff_dicts`), publishes `ConfigUpdated(diff=...)` on the bus.
- `logging/setup.py`: structlog with JSON or console renderer (TTY-aware), `app_version` + `pid` enrichers.
- `logging/bus_tap.py`: subscribes to the bus and logs each event with the brief's level map (`ErrorEvent` → ERROR; `TaskSubmitted/TaskCompleted/WakeDetected/LLMReplyComplete/TTSInterrupted/ConfigUpdated` → INFO; rest → DEBUG).
- `runtime.py`: `Runtime` async context manager. `start()` opens both subscriptions **synchronously** (then schedules the consumers as tasks) so any `publish` immediately after `start()` returns is delivered. `stop()` cancels tasks, closes the bus, awaits the reloader stop.
- `lifecycle.py`: `install_signal_handlers(runtime)` with a Windows fallback when `add_signal_handler` isn't available.

## Definition-of-done

Phase 0:

- [x] `packages/openmimicry-core/` installable via `pip install -e packages/openmimicry-core`.
- [x] Every Protocol and schema name from `contracts.md` exists in code with the exact signature.
- [x] `from openmimicry.core import LLMAdapter, STTAdapter, TTSAdapter, TaskRuntimeAdapter, AvatarRuntimeAdapter, AvatarDirective, RuntimeEvent, AppConfig` succeeds.
- [x] Sibling package directories exist with stub `mocks.py` raising `NotImplementedError`.
- [x] `scripts/check_imports.py` passes on the current tree.
- [x] `tests/contract/test_*.py` exist with parametrised fixtures and `pytest.skip` bodies.
- [x] `tests/unit/core/test_schemas.py` passes.
- [x] `ruff check` clean; `ruff format --check` clean.
- [x] `CHANGELOG.md` already has the Phase 0 entry.
- [ ] PR labelled `phase-0` and `breaking`.

M0:

- [x] Every file under "Outputs" exists.
- [x] Unit tests pass (84 unit + 26 contract-skips).
- [x] `EventBus` correctly fans out with the documented drop policy.
- [x] `AppConfig` loads from YAML, accepts env overrides via `OPENMIMICRY__...`, accepts a profile overlay.
- [x] `ConfigUpdated` is published when the loader returns a changed config (covered by `test_config_reloader.test_reload_once_publishes_diff_when_changed`).
- [x] `RuntimeStore` is immutable; mutation attempts raise `ValidationError`.
- [x] `Runtime` works as an `async with` context manager.
- [x] `scripts/check_imports.py` is clean.
- [ ] `make ci` green on Ubuntu + Windows (verify in CI).

## Verification done locally

```text
84 passed, 26 skipped (contract suites awaiting M1-M5) in 1.1 s
scripts/check_imports.py: OK
ruff check: All checks passed!
ruff format --check: 54 files already formatted
```

## Files

66 files changed, ~4 600 LOC added. New tree:

```text
packages/
  openmimicry-core/
    pyproject.toml, README.md
    src/openmimicry/core/{__init__,bus,store,runtime,lifecycle}.py
    src/openmimicry/core/contracts/{__init__,bus,llm,voice,tasks,avatar}.py
    src/openmimicry/core/schemas/{__init__,events,llm,voice,tasks,avatar,app}.py
    src/openmimicry/core/config/{__init__,loader,migrations,reloader}.py
    src/openmimicry/core/logging/{__init__,setup,bus_tap}.py
  openmimicry-{llm,voice,avatar,tasks}/
    pyproject.toml, README.md
    src/openmimicry/<name>/{__init__,mocks}.py
tests/
  conftest.py, fixtures/configs/minimal.yaml
  contract/{conftest,test_llm,test_stt,test_tts,test_speech_controller,test_task_runtime,test_avatar_runtime}.py
  unit/core/{test_bus,test_store,test_runtime,test_config_loader,test_config_reloader,test_logging,test_schemas,test_imports}.py
```

## Notes for review

- `EventBus.subscribe()` is **synchronous** per `contracts.md` §2.2 — registration must happen at call time so producers don't race the consumer's first `__anext__`. The `Runtime` relies on this when wiring `store_updater` and `bus_tap_loop`.
- `RuntimeStore.update()` is intentionally a no-op for events it doesn't care about, so the store-updater task can just funnel the whole bus through it.
- The `ConfigReloader` injects a `loader: Callable[[], AppConfig]` to keep unit tests deterministic; the production wiring calls `lambda: load(self._path)`.
- `pyproject.toml` gains `UP017`, `RUF002`, `RUF003` to the project-wide ruff ignore list — `datetime.UTC` would force a 3.11-only floor in places that don't need it, and the en-dash usage in docstrings is intentional throughout the project.

## What's next

This PR unlocks M1 (`openmimicry-llm` / LiteLLM), M2 (`openmimicry-voice` / RealtimeSTT/TTS), M3+M4 (avatar core + Sprite2D), M5 (`openmimicry-tasks` / mcp-agent + Claude Code) — they each pick up against this immutable surface in parallel.
