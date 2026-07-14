# Module M3: `openmimicry-avatar` (core)

## Goal (1 line)

Implement the character-pack loader and validator, the `AvatarDirector` state machine, the `AvatarOrchestrator`, and the `MockAvatarRuntimeAdapter` — the substrate every concrete avatar runtime (M4 Sprite2D, M9 Three.js, post-v0.2 modalities) will plug into.

## Scope and non-scope

**In scope.**

- `CharacterPack` loader (`load_pack(path) -> CharacterPack`) with full validation against `PackSchema`.
- `validate_pack(path)` CLI as `scripts/validate_pack.py`.
- `AvatarDirector` concrete: the state machine that turns `RuntimeEvent` into `AvatarDirective`.
- `AvatarOrchestrator` concrete: holds the active `AvatarRuntimeAdapter`, subscribes to the bus, dispatches directives, and supports `swap_runtime(...)`.
- `MockAvatarRuntimeAdapter` — canonical fixture other modules consume.
- A pack-fallback policy (missing emotion → default emotion, missing `_speaking` variant → base emotion).

**Non-scope.**

- The Sprite2D rendering itself (M4 owns).
- Any 3D / Three.js / Unity rendering (M9 / M11 own).
- The frontend's runtime adapter registry (M7 owns).
- LLM/voice/task wiring (M6 owns).

## Inputs (immutable, from contracts.md)

- `AvatarRuntimeAdapter`, `AvatarDirector`, `AvatarOrchestrator` Protocols (`contracts.md` §5).
- Schemas: `AvatarDirective`, `State`, `Emotion`, `CharacterPack`, `EmotionFrames` (`contracts.md` §2.3, §2.4).
- `RuntimeEvent` (`contracts.md` §2.1).
- `EventBus` (M0).
- `AvatarConfig` sub-config from `AppConfig.avatar` ([`../configuration.md`](../configuration.md)).

## Outputs (this module owns)

```text
packages/openmimicry-avatar/
  pyproject.toml
  README.md
  src/openmimicry/avatar/
    __init__.py
    runtimes/
      __init__.py
      base.py           # re-export of AvatarRuntimeAdapter
    pack/
      __init__.py
      loader.py         # load_pack(path)
      validator.py      # validate_pack(path) -> ValidationReport
    director.py         # AvatarDirector concrete
    orchestrator.py     # AvatarOrchestrator concrete
    mocks.py            # MockAvatarRuntimeAdapter
scripts/validate_pack.py   # thin CLI wrapper around pack.validator
tests/unit/avatar/
  test_pack_loader.py
  test_pack_validator.py
  test_director.py
  test_orchestrator.py
  test_mock_runtime.py
tests/fixtures/packs/
  good_pack/             # tiny synthetic pack used in tests
  missing_speaking/      # exercises fallback rule
  broken_manifest/       # exercises validator error path
tests/contract/test_avatar_runtime.py   # un-skipped (mock only at this stage)
```

## Mock implementations this module provides

```python
# openmimicry.avatar.mocks
class MockAvatarRuntimeAdapter:
    name: str = "mock"
    capabilities: set[str] = {"mock"}
    directives_received: list[AvatarDirective]
    is_visible: bool
    is_speaking: bool
    last_text: str | None

    def __init__(self) -> None: ...

    async def load_character(self, character_id: str, config: dict) -> None: ...
    async def apply_directive(self, directive: AvatarDirective) -> None: ...
    async def set_text(self, text: str) -> None: ...
    async def start_speaking(self, text: str | None = None) -> None: ...
    async def stop_speaking(self) -> None: ...
    async def set_visibility(self, visible: bool) -> None: ...
    async def healthcheck(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

`MockAvatarRuntimeAdapter` records everything. M6 integration tests assert on `directives_received` to confirm the right sequence of states fired.

## Test surface

- **Unit.** `load_pack(tests/fixtures/packs/good_pack)` returns a `CharacterPack` with all emotions present.
- **Unit.** `load_pack(tests/fixtures/packs/missing_speaking)` succeeds but emits a deprecation-style warning per missing `_speaking` variant.
- **Unit.** `validate_pack(tests/fixtures/packs/broken_manifest)` returns a `ValidationReport(ok=False, errors=[...])`.
- **Unit.** `AvatarDirector.on_event(UserSpeechStarted())` → `AvatarDirective(state="listening")`. Full table from `../character_packs.md` §4 covered.
- **Unit.** Hold-and-return: feeding `TaskCompleted` produces `happy`; after `hold_ms`, the next idle event returns `idle`.
- **Unit.** `AvatarOrchestrator.swap_runtime(new)` calls `old.shutdown()`, `new.load_character(...)`, then re-emits the *current* directive to `new` so the visual state matches.
- **Contract.** `tests/contract/test_avatar_runtime.py` exercises `MockAvatarRuntimeAdapter`: `apply_directive` accepts any well-formed `AvatarDirective` (including ones with `gesture`/`gaze` fields the adapter doesn't understand — must not raise).

## Step-by-step plan (atomic, numbered)

1. Create `packages/openmimicry-avatar/pyproject.toml`. No optional deps (M4, M9, etc. add their own packages or extras).
2. Replace Phase 0 stub `mocks.py`. Implement `MockAvatarRuntimeAdapter` per the signature above.
3. Implement `pack/loader.py::load_pack(path: Path) -> CharacterPack`. Read `pack.yaml`, validate against the `CharacterPack` Pydantic model, expand relative paths, sort-and-list frame files when `frames` is a folder.
4. Implement `pack/validator.py::validate_pack(path) -> ValidationReport`. Reports: missing files, missing emotion folders, missing `_speaking` variants (warning, not error), wrong schema_version, invalid YAML. Used by both the loader and the CLI.
5. Implement `scripts/validate_pack.py`. Thin argparse wrapper; exits 1 on any error.
6. Implement `director.py::AvatarDirector`. The state-machine table from `character_packs.md` §4. Hold-and-return scheduler uses an internal `asyncio.TimerHandle`; firing the timer publishes a synthetic "return-to-idle" via the bus (not via direct mutation).
7. Implement `orchestrator.py::AvatarOrchestrator`:
   - Holds `director`, `runtime: AvatarRuntimeAdapter`, `bus`, `cfg: AvatarConfig`, `_current: AvatarDirective`.
   - `start()` subscribes to the bus; for each event, calls `director.on_event`; if non-None, awaits `runtime.apply_directive(d)` and stores it.
   - `stop()` unsubscribes and calls `runtime.shutdown()`.
   - `swap_runtime(new)`: pause subscription, call `old.shutdown()`, call `new.load_character(cfg.pack, cfg.runtimes[new.name].model_dump())`, re-emit `self._current` via `new.apply_directive(self._current)`, resume.
8. Build `tests/fixtures/packs/good_pack/` with a real (tiny) PNG per state. Two emotions are enough (`idle`, `happy`, each with `_speaking` variant).
9. Write unit tests including the full state-machine table.
10. Un-skip `tests/contract/test_avatar_runtime.py` for `MockAvatarRuntimeAdapter`. Add `pytest.skipif` placeholders for `sprite2d`, `threejs`, etc. so they activate when M4/M9 register.
11. Register `MockAvatarRuntimeAdapter` via entry point `openmimicry.contracts.avatar_runtime`.
12. Write `packages/openmimicry-avatar/README.md` with a 20-line example: load `octomimic`, attach to a `MockAvatarRuntimeAdapter`, publish a `UserSpeechStarted`, assert the mock received `AvatarDirective(state="listening")`.
13. Update `CHANGELOG.md`.
14. `make ci`. Open PR `feat(avatar): M3 — pack loader, director, orchestrator, mock runtime`.

## Definition of done (checklist)

- [ ] `from openmimicry.avatar import load_pack, AvatarDirector, AvatarOrchestrator, MockAvatarRuntimeAdapter` works.
- [ ] `python scripts/validate_pack.py characters/octomimic/` exits 0; `characters/mimic_blue/` exits 0.
- [ ] Director state-machine table from `character_packs.md` §4 is covered cell-by-cell in unit tests.
- [ ] Hold-and-return for `happy` and `error` is tested with frozen time.
- [ ] `AvatarOrchestrator.swap_runtime` preserves visual state (the re-emit invariant).
- [ ] `MockAvatarRuntimeAdapter` passes the contract test.
- [ ] Coverage ≥ 85% on `openmimicry-avatar` source.
- [ ] `scripts/check_imports.py` clean.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M3 (`openmimicry-avatar` core)** of OpenMimicry. The Protocols and schemas are frozen.
>
> Read in order:
>
> 1. `docs/contracts.md` §2.3, §2.4, §5 — `AvatarDirective`, `CharacterPack`, the avatar Protocols.
> 2. `docs/modules/M3_avatar_core.md` — this brief.
> 3. `docs/character_packs.md` — pack format, the state-machine table you must implement verbatim, fallback rules.
> 4. `docs/avatar_modalities.md` §2, §4 — how the orchestrator and runtime adapters compose. (You do NOT implement Sprite2D / Three.js here; that's M4 / M9. You only build the substrate.)
> 5. `docs/event_flows.md` — what events you must react to.
>
> Implement the 14-step plan. The state-machine table in `character_packs.md` §4 is the executable spec; reproduce every cell.
>
> Ship `MockAvatarRuntimeAdapter` early — M6 (backend), M4 (Sprite2D), and the integration suite all consume it. Make sure it records `directives_received` so tests can assert sequences.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-tasks`. Only `openmimicry-core`. Open the PR titled `feat(avatar): M3 — pack loader, director, orchestrator, mock runtime` with the Definition-of-done checklist ticked.
