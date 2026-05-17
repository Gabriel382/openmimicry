# feat(avatar): M3 — pack loader, director, orchestrator, mock runtime

Lands `openmimicry-avatar` per `docs/modules/M3_avatar_core.md`. M3 ships the substrate every concrete avatar runtime (M4 Sprite2D, M9 Three.js, M10–M12 modalities) will plug into.

## What's in the box

### Pack loader & validator

- `openmimicry.avatar.pack.load_pack(path) -> CharacterPack` — reads `pack.yaml`, validates against the frozen Pydantic schema, resolves `frames` / `speaking_frames` (folder or explicit list) against the pack root.
- Fallback rules from `docs/character_packs.md` §6:
  - Missing `_speaking` for state S → fall back to S's base frames, log a warning.
  - Missing referenced folder/file → raise `PackLoadError`.
  - Invalid YAML / failed schema validation → raise `PackLoadError`.
- `openmimicry.avatar.pack.validate_pack(path) -> ValidationReport` — non-raising; used by both the loader and the CLI. Errors block; warnings don't.
- `scripts/validate_pack.py` — argparse CLI; exits 1 on any error; `--strict` promotes warnings; accepts pack dirs or roots-of-packs.

### Director (state machine)

- `AvatarDirector.on_event(RuntimeEvent) -> AvatarDirective | None` implements the table in `docs/character_packs.md` §4 **cell by cell**. The table is reproduced verbatim in `test_director.py::TABLE` and exercised via `@pytest.mark.parametrize`.
- Hold-and-return: `happy` / `error` directives carry `next_state="idle"` + `duration_ms` (`celebration_ms` / `error_ms` from `AvatarConfig`).
- Emotion mapping: `thinking → focused`, `happy → happy`, `error → worried`, everything else `neutral`.
- Soft handling for events the table doesn't enumerate (`UserTextSubmitted`, `WakeDetected`, `LLMReplyComplete`, `TranscriptPreview`): transition to `thinking` when appropriate, otherwise no-op.
- `apply_return_to(state)` is the synthetic directive the orchestrator uses when a hold timer fires.

### Orchestrator

- `AvatarOrchestrator(director=, runtime=, bus=, config=)` subscribes to the bus on `start()` and dispatches `AvatarDirective`s onto the active runtime.
- Calls `runtime.load_character(cfg.pack, cfg.runtimes[runtime.name])` during `start()`.
- Hold-and-return is scheduled with `loop.call_later`; the timer creates an async task that asks the director for `apply_return_to(next_state)` and dispatches that directive. Any **newer** directive cancels the pending timer (via `_cancel_return_timer`).
- **`swap_runtime(new)` invariant** (DoD): `old.shutdown()` → `new.load_character(...)` → `new.apply_directive(self._current)` so visual state survives the swap.
- `runtime.apply_directive` exceptions are logged and swallowed (the consumer never crashes the runtime).

### Mock runtime

- `MockAvatarRuntimeAdapter` replaces the Phase 0 `NotImplementedError` stub. Records every directive into `directives_received`. Accepts unknown fields (`gesture` / `gaze` / `intensity`) without raising. Tracks `is_visible`, `is_speaking`, `last_text`, `loaded_character`, `last_character_config`, `load_calls`, `shutdown_calls`. Registers via `openmimicry.contracts.avatar_runtime`.

## Tests

`tests/unit/avatar/` adds:

- `test_mock_runtime.py` — Protocol satisfaction, directive recording, unknown-field tolerance, speaking/visibility/text/shutdown lifecycle.
- `test_pack_loader.py` — good pack loads with all emotions; missing-speaking falls back with warning; broken manifest raises; missing dir / missing YAML / invalid YAML; explicit-list `frames` resolution.
- `test_pack_validator.py` — good pack passes; missing-speaking is a warning; broken manifest reports errors; summary string.
- `test_director.py` — **parametrised over every cell** of the §4 table (42 parametrised cases), plus hold-and-return assertions and emotion-mapping checks.
- `test_orchestrator.py` — `start()` loads character, bus events produce directives, TTS cycle drives speaking→idle, hold-and-return for `happy`, `swap_runtime` preserves visual state, idempotent stop, `runtime.apply_directive` errors are logged not raised.

`tests/fixtures/packs/`:

- `good_pack/` — 2 emotions × 2 frame folders each (zero-byte `.png` placeholders).
- `missing_speaking/` — same emotions but no `_speaking` variants (exercises the fallback rule).
- `broken_manifest/` — missing required `id`/`name` + references a nonexistent folder (exercises the validator error path).

`tests/contract/test_avatar_runtime.py` is **un-skipped**: Protocol isinstance, healthcheck shape, hermetic `apply_directive` round-trip (including unknown fields), `shutdown` idempotency, capabilities-set shape.

## Definition-of-done checklist

- [x] `from openmimicry.avatar import load_pack, AvatarDirector, AvatarOrchestrator, MockAvatarRuntimeAdapter` works.
- [x] `scripts/validate_pack.py` exists and is wired into `make validate-packs`.
- [x] Director state-machine table from `docs/character_packs.md` §4 is covered cell-by-cell.
- [x] Hold-and-return for `happy` (and the `error` analog) is tested.
- [x] `AvatarOrchestrator.swap_runtime` preserves visual state (re-emit invariant tested).
- [x] `MockAvatarRuntimeAdapter` passes the contract test.
- [x] `scripts/check_imports.py` clean — `openmimicry-avatar` depends only on `openmimicry-core`.
- [x] `CHANGELOG.md` entry added.

## Files

```
packages/openmimicry-avatar/
  pyproject.toml                                    [entry point + pyyaml dep]
  README.md
  src/openmimicry/avatar/
    __init__.py                                     [re-exports]
    py.typed
    mocks.py                                        [replaces Phase 0 stub]
    director.py                                     [state machine]
    orchestrator.py                                 [bus consumer + swap_runtime]
    runtimes/{__init__,base}.py                     [AvatarRuntimeAdapter re-export]
    pack/{__init__,loader,validator}.py             [pack tooling]
tests/unit/avatar/
  __init__.py
  test_mock_runtime.py
  test_pack_loader.py
  test_pack_validator.py
  test_director.py                                  [42 parametrised state-machine cells]
  test_orchestrator.py
tests/fixtures/packs/
  good_pack/{pack.yaml,states/...}
  missing_speaking/{pack.yaml,states/...}
  broken_manifest/pack.yaml
tests/contract/test_avatar_runtime.py               [un-skipped]
scripts/validate_pack.py                            [CLI]
Makefile                                            [validate-packs hooks new script]
.github/workflows/ci.yml                            [lint scope adds validate_pack.py]
CHANGELOG.md                                        [M3 entry]
```

## Labels

`module:avatar`, `m3`
