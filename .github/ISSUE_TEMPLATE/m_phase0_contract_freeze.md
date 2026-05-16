---
name: "Phase 0: Contract freeze"
about: Translate docs/contracts.md into runnable Python — Protocols, schemas, mocks, contract tests
title: "[Phase 0] Contract freeze — Protocols, schemas, contract tests"
labels: ["module", "phase-0", "blocking", "breaking"]
assignees: []
---

## Overview

Land `docs/contracts.md` as runnable code under `packages/openmimicry-core/`, shipping the frozen Protocols, Pydantic schemas, canonical mock skeletons, and parametrised contract tests so every other module can be developed in parallel against an immutable surface.

**Status: blocking.** No other module (M0–M9, M10–M12) can start until this lands. MX (tooling) can run in parallel.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) — the immutable interface set. You are translating this verbatim.
2. [`docs/modules/M_phase0_contract_freeze.md`](../docs/modules/M_phase0_contract_freeze.md) — the full brief.
3. [`docs/parallel_execution.md`](../docs/parallel_execution.md) §3 — rules of engagement.

## LLM brief

> You are implementing **Phase 0 (Contract freeze)** of OpenMimicry, a modular avatar interface layer.
>
> Read these three files first, in order:
>
> 1. `docs/contracts.md` — the immutable interface set. Your job is to translate this file into runnable Python.
> 2. `docs/modules/M_phase0_contract_freeze.md` — the brief.
> 3. `docs/parallel_execution.md` §3 — the rules of engagement.
>
> Then produce the file tree listed in the "Outputs" section of the brief, following the 23-step plan verbatim. Do not invent new types, do not add fields not listed in `contracts.md`, do not skip any class. Every Protocol must be `@runtime_checkable`. Every schema must be Pydantic v2 with `model_config = ConfigDict(frozen=True)`.
>
> When you're done, run `make lint`, `make typecheck`, and `pytest -q`. Fix anything that fails before opening the PR.
>
> Open the PR titled `feat(core): Phase 0 contract freeze` with the "Definition of done" checklist in the description, every item ticked.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, or `openmimicry-tasks` source — only their `mocks.py` stubs you yourself create. If you discover an ambiguity in `contracts.md`, stop and ask before making a unilateral decision. The whole parallel plan depends on this file being faithful.

## Definition of done

See [`docs/modules/M_phase0_contract_freeze.md`](../docs/modules/M_phase0_contract_freeze.md) "Definition of done". The PR description must check every box.

## Acceptance

- [ ] PR labelled `phase-0` and `breaking`.
- [ ] Two-person rule: requires two approving reviews (per [`MAINTAINERS.md`](../MAINTAINERS.md)).
- [ ] `make ci` green on Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry under `## [Unreleased]`.
