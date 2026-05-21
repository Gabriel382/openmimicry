# Module Phase 0: Contract freeze

## Goal (1 line)

Land `contracts.md` as runnable code under `packages/openmimicry-core/`, shipping the frozen Protocols, Pydantic schemas, canonical mocks, and parametrised contract tests so that every other module can be developed in parallel against an immutable surface.

## Scope and non-scope

**In scope.**

- Create the `packages/openmimicry-core/` workspace package and its `pyproject.toml`.
- Translate every Python type listed in [`../contracts.md`](../contracts.md) §1–§7 into runnable code under:
  - `packages/openmimicry-core/src/openmimicry/core/contracts/{llm,voice,tasks,avatar,bus}.py`
  - `packages/openmimicry-core/src/openmimicry/core/schemas/{events,llm,voice,tasks,avatar,app}.py`
- Ship the canonical **mock skeleton signatures** referenced in `contracts.md` §8. The full mock implementations live in the respective module briefs (M1–M5); Phase 0 only ships the import-stable stubs so other modules can target them.
- Ship the **parametrised contract test files** in `tests/contract/` listed in `contracts.md` §10. They must be runnable; they may be empty-bodied (`pytest.skip`) where the implementation has not yet been written, but the fixture machinery and parametrisation must work.
- Add `scripts/check_imports.py` that walks `packages/*` and fails if any source file imports from a sibling package (only `openmimicry.core.*` is allowed).
- Add a `CHANGELOG.md` entry under `## Unreleased` describing the freeze.

**Non-scope.**

- No concrete adapter implementations (no LiteLLM, no RealtimeSTT, no Sprite2D). Those are M1, M2, M4 respectively.
- No `EventBus` runtime behaviour beyond the Protocol/class signature. The implementation is in M0.
- No `AppConfig` loader logic. M0 owns that. Phase 0 only ships the schema models.
- No backend wiring, no frontend, no Tauri.

## Inputs (immutable, from contracts.md)

Phase 0 has no inputs — it **produces** the inputs that every other module consumes. The source of truth Phase 0 must translate faithfully is [`../contracts.md`](../contracts.md).

## Outputs (this module owns)

```text
packages/openmimicry-core/
  pyproject.toml
  src/openmimicry/core/
    __init__.py
    contracts/
      __init__.py
      bus.py            # EventBus class signature
      llm.py            # LLMAdapter Protocol
      voice.py          # STTAdapter, TTSAdapter, SpeechController, WakeController
      tasks.py          # TaskRuntimeAdapter
      avatar.py         # AvatarRuntimeAdapter, AvatarDirector, AvatarOrchestrator
    schemas/
      __init__.py
      events.py         # RuntimeEvent union + all variants
      llm.py
      voice.py
      tasks.py
      avatar.py         # AvatarDirective, State, Emotion, CharacterPack, EmotionFrames
      app.py            # AppConfig + sub-configs
tests/
  contract/
    __init__.py
    conftest.py         # registers installed implementations via entry points
    test_llm.py
    test_stt.py
    test_tts.py
    test_speech_controller.py
    test_task_runtime.py
    test_avatar_runtime.py
scripts/
  check_imports.py
```

`packages/openmimicry-core` is published as a path dependency from the workspace root `pyproject.toml`. After Phase 0 lands, `pip install -e packages/openmimicry-core` succeeds and `from openmimicry.core.contracts.llm import LLMAdapter` works.

## Mock implementations this module provides

Phase 0 does **not** ship runnable mocks. It ships **mock module stubs** that the M1–M5 briefs are responsible for fleshing out. The stubs are placeholder classes with the right names and the right surface so other modules can write `from openmimicry.llm.mocks import MockLLMAdapter` and have it import (raising `NotImplementedError` on use until M1 lands).

The stub files live in each sibling package's planned tree — Phase 0 creates only the directory placeholders and `__init__.py` files for those packages:

```text
packages/openmimicry-llm/src/openmimicry/llm/mocks.py    # stub
packages/openmimicry-voice/src/openmimicry/voice/mocks.py # stub
packages/openmimicry-avatar/src/openmimicry/avatar/mocks.py # stub
packages/openmimicry-tasks/src/openmimicry/tasks/mocks.py  # stub
```

Each stub raises `NotImplementedError("Implemented by Mx; see docs/modules/Mx_*.md.")` on construction so misuse is loud.

## Test surface

- **Unit.** `tests/unit/core/test_schemas.py` — round-trip every Pydantic schema through JSON and back; confirm `frozen=True`; confirm `RuntimeEvent` discriminator works (parse by `kind`).
- **Contract.** `tests/contract/conftest.py` defines a `pytest.fixture` `implementations(protocol_name)` that loads any class registered under entry point group `openmimicry.contracts.<protocol_name>`. Each contract test file iterates over those implementations.
- **Import hygiene.** `tests/unit/core/test_imports.py` runs `scripts/check_imports.py` and asserts a clean exit.

The Phase 0 PR ships contract tests with their fixture machinery wired up but their assertion bodies marked `pytest.skip("implemented in Mx")`. M1–M5 PRs are responsible for un-skipping their respective sections.

## Step-by-step plan (atomic, numbered)

1. Create `packages/openmimicry-core/pyproject.toml` with `name = "openmimicry-core"`, `version = "0.2.0a0"`, dependency on `pydantic>=2.7`. Set `[tool.setuptools.packages.find] where = ["src"]`.
2. Create empty `__init__.py` files for `openmimicry`, `openmimicry.core`, `openmimicry.core.contracts`, `openmimicry.core.schemas`.
3. Implement `openmimicry/core/schemas/events.py`: copy every class from `contracts.md` §2.1 verbatim. Add `__all__`. Add `model_config = ConfigDict(frozen=True)` where needed (Pydantic v2 syntax).
4. Implement `openmimicry/core/schemas/llm.py` from `contracts.md` §3.
5. Implement `openmimicry/core/schemas/voice.py` from `contracts.md` §4.
6. Implement `openmimicry/core/schemas/tasks.py` from `contracts.md` §6.
7. Implement `openmimicry/core/schemas/avatar.py` from `contracts.md` §2.3 and §2.4.
8. Implement `openmimicry/core/schemas/app.py` from `contracts.md` §7 plus the leaf models cited in `../configuration.md`. Defer concrete validators to M0.
9. Implement `openmimicry/core/contracts/bus.py`: the `EventBus` class with `publish`, `subscribe`, `aclose` signatures and `raise NotImplementedError("provided by M0 core")`.
10. Implement `openmimicry/core/contracts/llm.py`: `LLMAdapter` Protocol from `contracts.md` §3, decorated with `@runtime_checkable`.
11. Implement `openmimicry/core/contracts/voice.py`: `STTAdapter`, `TTSAdapter`, `SpeechController`, `WakeController` Protocols from `contracts.md` §4.
12. Implement `openmimicry/core/contracts/tasks.py`: `TaskRuntimeAdapter` Protocol from `contracts.md` §6.
13. Implement `openmimicry/core/contracts/avatar.py`: `AvatarRuntimeAdapter`, `AvatarDirector`, `AvatarOrchestrator` Protocols from `contracts.md` §5.
14. Add `openmimicry/core/__init__.py` re-exports of every contract Protocol and every schema for ergonomic `from openmimicry.core import LLMAdapter, AvatarDirective`.
15. Create the four sibling-package directories with their `pyproject.toml`, `src/openmimicry/<name>/__init__.py`, and stub `mocks.py` files. Each `pyproject.toml` declares a path dependency on `openmimicry-core`.
16. Implement `scripts/check_imports.py`: walk `packages/*/src/`, AST-parse each `.py`, fail if any `from openmimicry.<x>` import refers to a sibling package (only `openmimicry.core` is allowed) — except in test files and `mocks.py`.
17. Implement `tests/contract/conftest.py` with a fixture that yields registered implementations by reading entry points group `openmimicry.contracts.<protocol_name>`. Provide a fallback that yields nothing if none are registered.
18. Implement skeletons for `tests/contract/test_{llm,stt,tts,speech_controller,task_runtime,avatar_runtime}.py`. Each file has the canonical test names (`test_healthcheck_returns_bool`, `test_generate_streams_at_least_one_chunk`, etc.) and `pytest.skip("awaiting Mx")` bodies.
19. Implement `tests/unit/core/test_schemas.py`: instantiate every event class, round-trip through JSON, assert `frozen=True` raises on mutation, assert `RuntimeEvent` discriminated parsing.
20. Add the workspace root `pyproject.toml` workspace declaration (`[tool.uv.workspace]` or `[tool.hatch.workspace]` depending on chosen manager).
21. Add `CHANGELOG.md` entry: `### Added — Phase 0 contract freeze. Schemas, Protocols, contract test scaffolding.`
22. Run `make lint && make typecheck && pytest -q`. All green.
23. Open the PR: `feat(core): Phase 0 contract freeze — Protocols, schemas, contract tests`.

## Definition of done (checklist)

- [ ] `packages/openmimicry-core/` installable via `pip install -e packages/openmimicry-core`.
- [ ] Every Protocol and schema name from `contracts.md` exists in the codebase with the exact signature.
- [ ] `from openmimicry.core import LLMAdapter, STTAdapter, TTSAdapter, TaskRuntimeAdapter, AvatarRuntimeAdapter, AvatarDirective, RuntimeEvent, AppConfig` succeeds.
- [ ] Sibling package directories exist with stub `mocks.py` that raise `NotImplementedError`.
- [ ] `scripts/check_imports.py` exists and passes on the current tree.
- [ ] `tests/contract/test_*.py` files exist with parametrised fixtures and `pytest.skip` bodies.
- [ ] `tests/unit/core/test_schemas.py` passes.
- [ ] `ruff check`, `ruff format --check`, `pyright`, `pytest -q` all clean.
- [ ] `CHANGELOG.md` has the Phase 0 entry.
- [ ] PR labelled `phase-0` and `breaking` (because there was no previous version to break).

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Phase 0 (Contract freeze)** of OpenMimicry, a modular avatar interface layer.
>
> Read these three files first, in order:
>
> 1. `docs/contracts.md` — the immutable interface set. Your job is to translate this file into runnable Python.
> 2. `docs/modules/M_phase0_contract_freeze.md` — this brief.
> 3. `docs/parallel_execution.md` §3 — the rules of engagement.
>
> Then produce the file tree listed in the "Outputs" section of the brief, following the 23-step plan verbatim. Do not invent new types, do not add fields not listed in `contracts.md`, do not skip any class. Every Protocol must be `@runtime_checkable`. Every schema must be Pydantic v2 with `model_config = ConfigDict(frozen=True)`.
>
> When you're done, run `make lint`, `make typecheck`, and `pytest -q`. Fix anything that fails before opening the PR.
>
> Open the PR titled `feat(core): Phase 0 contract freeze` with the "Definition of done" checklist in the description, every item ticked.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, or `openmimicry-tasks` source — only their `mocks.py` stubs you yourself create. If you discover an ambiguity in `contracts.md`, stop and ask before making a unilateral decision. The whole parallel plan depends on this file being faithful.
