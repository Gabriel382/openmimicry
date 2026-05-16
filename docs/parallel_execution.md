# Parallel execution plan

This document is the workflow for building OpenMimicry across multiple independent LLM sessions (or contributors). Each module is a self-contained brief in `docs/modules/Mx_*.md`. A single LLM agent (Claude, GPT-class, local model, or human) can pick up one brief, implement it against the frozen interfaces, and open a PR — without ever reading another module's source.

That guarantee comes from one rule: **the interfaces are frozen first, in [`contracts.md`](./contracts.md), and never change without a coordinated version bump.**

## 1. The workflow

```text
Phase 0  Interface freeze
   ↓
   Produces: contracts.md + the skeleton packages with Protocols + mock impls + contract tests
   These are immutable for the remainder of the parallel work.
   ↓
Phase 1  Parallel modules
   ↓
   M0  M1  M2  M3  M4  M5  M6  M7  M8  MX
   Each is its own PR. Each agent gets one brief + contracts.md.
   ↓
Phase 2  Assembly + smoke tests
   ↓
   Wire packages together in apps/backend. e2e tests run.
   ↓
Phase 3  Release v0.2.0
   ↓
Phase 4  Modality expansion (post-v0.2)
   M9 ThreeJS  M10 Live3D  M11 Unity  M12 External — also parallel.
```

## 2. The dependency graph

```text
                ┌────────────────────────┐
                │  Phase 0 contracts.md  │
                └────────────┬───────────┘
                             │  (immutable; everyone imports it)
              ┌──────────┬───┴──────┬──────────┬──────────┐
              ▼          ▼          ▼          ▼          ▼
            M0 core   M1 LLM    M2 voice   M3 avatar  M5 tasks
                                            │
                                            ▼
                                       M4 sprite2d
                                            │
                  ┌─────────────────────────┼─────────────────────────┐
                  ▼                         ▼                         ▼
              M6 backend             M7 frontend              M8 src-tauri
                  │                         │                         │
                  └─────────────────────────┴───────── M9 threejs (post)
                  (assembly: requires M0..M5 mocks at minimum)
                                            │
                                            ▼
                                  M10 live3d, M11 unity, M12 external
                                  (all post-v0.2.0, also parallel)

MX tooling is cross-cutting and can run in parallel with any phase.
```

The arrows are **runtime** dependencies. Every module only ever **imports from `openmimicry-core.contracts`** (the frozen Protocols and schemas) plus `openmimicry-core` itself for `EventBus` / `AppConfig` / `RuntimeStore`. They do **not** import from sibling packages — they consume sibling **mocks** during development.

## 3. The rules of engagement

Each rule below is a hard constraint. If you break one, the parallel guarantee breaks.

1. **Interfaces are immutable.** Anything in `contracts.md` (and the matching code under `packages/openmimicry-core/src/openmimicry/core/contracts/`) is frozen. Changing a signature, a field, or a return type requires a coordinated version bump and a PR that updates every consumer. No module may unilaterally change a contract.

2. **Mock-first development.** Before any concrete adapter is written, every module ships a **mock implementation** of its own contract (e.g. `MockLLMAdapter`, `MockSTTAdapter`, `MockAvatarRuntimeAdapter`). Mocks live in `packages/<module>/src/openmimicry/<module>/mocks.py` and are part of the module's public surface. Other agents consume only these mocks.

3. **Contract tests are the executable spec.** `tests/contract/test_<module>.py` is written in Phase 0 alongside the contract. It exercises any implementation against the protocol. An adapter is "done" when its contract test passes. Agents can implement against tests instead of reading prose.

4. **No cross-module imports outside contracts.** A module's source may import from `openmimicry-core` and `openmimicry-core.contracts`. It MUST NOT import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, or `openmimicry-tasks` (except `openmimicry-core` itself). Test files MAY import sibling mocks; production source MAY NOT. The CI step `scripts/check_imports.py` enforces this.

5. **One module = one PR.** Each module file lists a "Definition of done" checklist. Don't bundle. Don't drift. If you discover a missing contract, open a separate "contracts amendment" PR first.

6. **Conventional Commits.** Every commit prefixed (`feat(llm):`, `fix(voice):`, `chore(ci):`, `docs(arch):`, `test(avatar):`, `refactor(core):`). Module scope = the directory name.

7. **Self-contained PRs.** A module PR must pass `make ci` from a fresh checkout with only that module's code changed (plus the test fixtures it owns). If your PR needs a sibling to land first, you're violating the contract.

8. **Documentation is part of the deliverable.** Every PR updates `CHANGELOG.md` under `## Unreleased` and adds an entry to the module's own `README.md` if behaviour changes. A PR that "only changes code" is incomplete.

## 4. The module brief template

Every file under `docs/modules/Mx_*.md` follows this exact structure so any LLM agent can parse it:

```text
# Module Mx: <name>

## Goal (1 line)
## Scope and non-scope
## Inputs (immutable, from contracts.md)
## Outputs (this module owns)
## Mock implementations this module provides
## Test surface
## Step-by-step plan (atomic, numbered)
## Definition of done (checklist)
## Recommended LLM brief (copy-pasteable prompt)
```

The **Recommended LLM brief** at the bottom of each module file is a self-contained prompt you can paste into a fresh Claude session, another model, or share with a contributor. It says exactly what to read, what to write, and what "done" looks like.

## 5. Handing a module to an agent

The minimum kit an agent needs:

1. **`docs/contracts.md`** — the immutable interface set, read-only.
2. **The module brief**, e.g. `docs/modules/M1_llm.md`.
3. **The Phase 0 skeleton** (already in `main` from the contract-freeze PR): `packages/openmimicry-<name>/` with stubs, `tests/contract/test_<name>.py`, `mocks.py`.
4. **The relevant top-level architecture doc**, e.g. `docs/adapters.md` for context.

The agent does not need to read sibling module sources. If they ask "what does the LLM adapter look like?", point them at `MockLLMAdapter` from contracts.md.

Example handoff prompt (this is just the bare scaffold; each module's full brief is in its own file):

> You are implementing Module M1 (openmimicry-llm) of OpenMimicry. Read `docs/contracts.md` and `docs/modules/M1_llm.md`. Implement `LiteLLMAdapter` and `LLMRouter` such that `tests/contract/test_llm.py` passes and `tests/unit/llm/` passes. Do not import from other openmimicry packages except `openmimicry-core` and `openmimicry-core.contracts`. Open a PR titled `feat(llm): LiteLLMAdapter + LLMRouter`. Stop and ask before changing anything in `docs/contracts.md`.

## 6. Conflict resolution

Even with frozen contracts, two situations need rules:

- **Contract gap discovered mid-module.** Stop. Open a "contracts amendment" PR that updates `contracts.md`, the Protocol code, the contract test, and every existing mock. Land it first. Then resume.
- **Mock skew.** If module A is written against a mock of module B that doesn't quite match what B ends up doing, the contract test failed somewhere upstream. Fix the contract test; both sides land their fixes against the same updated spec.
- **Two agents touch shared files.** They shouldn't. Only `apps/backend/wiring.py` and `apps/desktop/frontend/src/runtimes/` are touched by more than one module brief; both are coordinated through M6 / M7 explicitly.

## 7. What lives where

```text
docs/
  parallel_execution.md       This document.
  contracts.md                The immutable interface set.
  modules/
    MX_tooling.md             Ruff, pyright, pytest, CI. Cross-cutting.
    M0_core.md                openmimicry-core.
    M1_llm.md                 openmimicry-llm.
    M2_voice.md               openmimicry-voice.
    M3_avatar_core.md         openmimicry-avatar (director, orchestrator, contract, mock).
    M4_avatar_sprite2d.md     Sprite2DAvatarAdapter.
    M5_tasks.md               openmimicry-tasks.
    M6_backend.md             apps/backend.
    M7_frontend.md            apps/desktop/frontend.
    M8_tauri.md               apps/desktop/src-tauri.
    M9_avatar_threejs.md      ThreeJSAvatarAdapter (post-v0.2.0).
    post_v0_2_modalities.md   M10 Live3D, M11 Unity, M12 External.
```

## 8. Quality gates

Before merging any module PR:

- `make lint` (Ruff) clean.
- `make typecheck` (pyright) clean for that module.
- `make test` passes (unit + contract for that module; e2e only on `main`).
- Coverage threshold met (per `pyproject.toml` per package).
- `scripts/check_imports.py` passes (no cross-module imports).
- `CHANGELOG.md` under `## Unreleased` has the entry.
- The module's `Definition of done` checklist is fully ticked in the PR description.

These are checked by CI; reviewers don't need to re-verify them manually.

## 9. Why this works

The pattern — freeze interfaces, write contract tests, develop against mocks, assemble at the end — is how systems like the Linux kernel, Kubernetes, and any large microservice fleet get built by people who never coordinate directly. It scales horizontally because **the interface is the only thing everyone has to agree on**, and that agreement is captured in code, not in conversation.

For OpenMimicry, the upside is that you can:

- Spin up three Claude sessions in parallel: one on M1 (LLM), one on M2 (voice), one on M3 + M4 (avatar). Each gets a brief and `contracts.md`. They finish independently. You merge in any order.
- Hand the frontend (M7) to a different model, or to a designer, while the Python work continues.
- Drop a module brief into a GitHub issue and let a community contributor pick it up.

The cost is one well-spent up-front afternoon writing `contracts.md`. After that, every parallel hour is real parallelism, not coordination overhead.
