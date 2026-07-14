---
name: "MX: Cross-cutting tooling"
about: Ruff, pyright, pytest, pre-commit, GitHub Actions, releases — the quality floor
title: "[MX] Tooling baseline — Ruff, pyright, pytest, GH Actions"
labels: ["module", "MX", "ci", "good first issue"]
assignees: []
---

## Overview

Make the repository linted, type-checked, tested, and CI-gated before any feature code lands.

**Parallelism: independent.** MX has no code dependencies and can run alongside any other module. It is the only brief that can land before Phase 0.

## Required reading

1. [`docs/testing_and_ci.md`](../docs/testing_and_ci.md)
2. [`docs/modules/MX_tooling.md`](../docs/modules/MX_tooling.md)
3. [`docs/parallel_execution.md`](../docs/parallel_execution.md) §3 and §8

## LLM brief

> You are implementing **Module MX (Cross-cutting tooling)** of OpenMimicry. This module has no Python source code; it produces configuration and CI machinery so every other module can land against a stable quality floor.
>
> Read these files first, in order:
>
> 1. `docs/testing_and_ci.md` — the target state.
> 2. `docs/modules/MX_tooling.md` — this brief.
> 3. `docs/parallel_execution.md` §3 and §8 — rules of engagement and quality gates.
>
> Implement the 20-step plan. Do not invent new tooling; use exactly the tools listed (Ruff, pyright, pytest, ESLint, Vitest, `cargo fmt`/`clippy`, pre-commit, commitlint, Dependabot). When the brief gives a target like "`make ci` exits 0 on Ubuntu and Windows", that is the acceptance criterion — your PR is not done until the matrix is green.
>
> If `scripts/validate_pack.py` doesn't exist yet (M3 owns it), the `pack-lint.yml` workflow may be a stub that exits 0. Mark it `TODO: wire when M3 lands` in a comment.
>
> Open the PR titled `chore(ci): MX tooling baseline` with every Definition-of-done item ticked. Do not touch any file under `packages/*/src/` — that belongs to other modules.

## Definition of done

See [`docs/modules/MX_tooling.md`](../docs/modules/MX_tooling.md). PR description checks every box.

## Acceptance

- [ ] `make ci` green on Ubuntu + Windows.
- [ ] `pre-commit run --all-files` green.
- [ ] `CHANGELOG.md` entry.
