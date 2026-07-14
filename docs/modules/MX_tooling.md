# Module MX: Cross-cutting tooling

## Goal (1 line)

Make the repository linted, type-checked, tested, and CI-gated before any feature code lands, so every other module merges against a stable, automated quality floor.

## Scope and non-scope

**In scope.**

- Workspace-level Python tooling: Ruff, pyright, pytest, pytest-cov, pytest-xdist, pre-commit.
- Frontend tooling: ESLint, Prettier, Vitest, `tsc --noEmit`.
- Rust tooling: `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`.
- GitHub Actions workflows: `ci.yml`, `release.yml`, `pack-lint.yml`, `codeql.yml`, `docs.yml`.
- Pre-commit configuration (`.pre-commit-config.yaml`).
- Conventional Commits enforcement via `commitlint`.
- The `Makefile` targets: `make lint`, `make typecheck`, `make test`, `make ci`, `make doctor`, `make install PROFILE=...`.
- `scripts/check_imports.py` (created by Phase 0; MX wires it into CI).
- Coverage thresholds per package.
- Dependabot configuration.

**Non-scope.**

- The contract test files themselves — those are owned by Phase 0.
- Per-module unit tests — owned by each `Mx`.
- Release automation logic (changelog generation, tagging) is sketched here but the full implementation is part of M6/M8 polish before tagging v0.2.0.

## Inputs (immutable, from contracts.md)

None. MX is purely infrastructure and depends on no Protocol or schema. It is the **only** module brief that can land before Phase 0.

## Outputs (this module owns)

```text
pyproject.toml                     # workspace root: tool.ruff, tool.pytest, tool.coverage
pyrightconfig.json
.pre-commit-config.yaml
.github/
  workflows/
    ci.yml
    release.yml
    pack-lint.yml
    codeql.yml
    docs.yml
  dependabot.yml
.gitignore                         # refreshed
Makefile                           # refreshed
scripts/
  doctor.sh                        # `make doctor` implementation
apps/desktop/frontend/
  .eslintrc.cjs
  .prettierrc
  vitest.config.ts                 # if not already present
apps/desktop/src-tauri/
  rustfmt.toml
  clippy.toml                      # optional
CHANGELOG.md                       # initial scaffold
CODE_OF_CONDUCT.md                 # initial scaffold
.editorconfig
```

## Mock implementations this module provides

None. MX produces no Python code that other modules import. It produces configuration and CI machinery.

## Test surface

- **CI must run from a fresh checkout.** A reviewer can `git clone && make ci` and get a green result on a fresh container. MX's "test" is this very property.
- **Pre-commit hooks must run on a clean tree** without changes. `pre-commit run --all-files` exits 0 on a freshly merged branch.
- **`scripts/check_imports.py` integrated as a CI step.** Its dry run on the current tree exits 0.

## Step-by-step plan (atomic, numbered)

1. Add to root `pyproject.toml`:
   - `[tool.ruff]` with `line-length = 100`, `target-version = "py311"`, the standard rule selection (`E`, `F`, `I`, `B`, `UP`, `SIM`, `RUF`), and per-file ignores for tests.
   - `[tool.ruff.format]` enabling the formatter.
   - `[tool.pytest.ini_options]` with `addopts = "-ra -q --strict-markers"`, `testpaths = ["tests"]`, `markers = ["contract", "integration", "e2e"]`.
   - `[tool.coverage.run]` and `[tool.coverage.report]` with `fail_under = 70` workspace-wide; per-package overrides via individual `pyproject.toml`.
2. Add `pyrightconfig.json` with `"include": ["packages", "apps/backend"]`, `"strict": ["packages/openmimicry-core/src", "packages/openmimicry-llm/src", "packages/openmimicry-avatar/src/openmimicry/avatar/orchestrator", "packages/openmimicry-avatar/src/openmimicry/avatar/base"]`. Everything else stays `basic` until graduated.
3. Add `.pre-commit-config.yaml` with: ruff (lint + format), end-of-file-fixer, trailing-whitespace, check-yaml, commitlint (gitlint-style via `commitlint-pre-commit-hook`).
4. Add `.editorconfig` with sensible defaults (LF endings, 4-space Python, 2-space TS/JSON/YAML, final newline).
5. Refresh `Makefile`:
   - `make help`: prints targets.
   - `make install PROFILE=basic`: installs workspace + selected extras via `uv sync --extras <profile>` (or `pip install -e ".[<profile>]"` if `uv` not available).
   - `make lint`: `ruff check . && ruff format --check .` and `npm run lint --prefix apps/desktop/frontend`.
   - `make format`: `ruff format .` (write).
   - `make typecheck`: `pyright` and `tsc --noEmit -p apps/desktop/frontend`.
   - `make test`: `pytest -n auto`.
   - `make ci`: `make lint && make typecheck && make test`.
   - `make doctor`: runs `scripts/doctor.sh`.
   - `make backend`, `make frontend`, `make desktop`, `make dev`: unchanged from current prototype.
   - `make clean`.
6. Implement `scripts/doctor.sh`: print versions of `python`, `node`, `npm`, `cargo`, `rustc`, `tauri`, `ffmpeg`, `ollama`, plus existence of `OPENROUTER_API_KEY` env var (without value), plus whether `make install` was run. Print a green/red checklist.
7. Add `.github/workflows/ci.yml` as specified in `docs/testing_and_ci.md` §4. Matrix: `{ubuntu-latest, windows-latest} × {3.11, 3.12}`. Steps: checkout, setup-uv (or actions/setup-python + pip), `uv sync --all-packages`, `make lint`, `make typecheck`, `make test`. Separate jobs for frontend (`npm ci && npm run lint && npm run typecheck && npm test`) and Rust (`cargo fmt --check && cargo clippy && cargo test`).
8. Add `.github/workflows/release.yml`: triggers on tag `v*`. Steps: build wheels via `uv build` per package, build Tauri bundles via `tauri-action` for Windows + Linux, generate changelog via `git-cliff` or `release-please`, create GitHub Release with artifacts attached. (Full implementation may be deferred; MX ships the scaffold + smoke job.)
9. Add `.github/workflows/pack-lint.yml`: runs `python scripts/validate_pack.py` against every directory under `characters/`. Initial implementation may `exit 0` if `validate_pack.py` doesn't exist yet; it's wired up so that landing M3 turns it on.
10. Add `.github/workflows/codeql.yml`: default CodeQL setup for Python and JavaScript.
11. Add `.github/workflows/docs.yml`: build `mkdocs` site from `docs/` and deploy to GitHub Pages on push to `main`. Optional; can ship as a stub.
12. Add `.github/dependabot.yml`: weekly grouped updates for `pip`, `npm`, `cargo`, `github-actions`.
13. Set up branch protection guidance in `CONTRIBUTING.md`: require all `ci` checks before merge, require Conventional Commits, require linked issue.
14. Add initial `CHANGELOG.md` with a Keep-a-Changelog header and a `## [Unreleased]` section.
15. Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 unchanged).
16. Add or refresh `apps/desktop/frontend/.eslintrc.cjs` (React + TypeScript), `.prettierrc`, ensure `npm run lint`, `npm run typecheck`, `npm run test` scripts exist in `package.json`.
17. Add `rustfmt.toml` under `apps/desktop/src-tauri/` (or repo root). Trivial config.
18. Run `pre-commit install` instructions added to `CONTRIBUTING.md` so contributors auto-enroll.
19. Verify: clone fresh, `make install PROFILE=basic && make ci` → green. Commit fixes for whatever isn't.
20. Open the PR: `chore(ci): MX tooling baseline — ruff, pyright, pytest, GH Actions`.

## Definition of done (checklist)

- [ ] `make lint` exits 0 on a clean tree.
- [ ] `make typecheck` exits 0 on a clean tree.
- [ ] `make test` exits 0 on a clean tree (skipped tests count as pass).
- [ ] `make ci` exits 0 on Ubuntu and Windows in GitHub Actions.
- [ ] `pre-commit run --all-files` exits 0.
- [ ] `make doctor` prints a readable checklist.
- [ ] `.github/workflows/ci.yml` runs on every PR.
- [ ] `.github/workflows/release.yml` exists and is gated to tag events.
- [ ] `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `.editorconfig` exist.
- [ ] `dependabot.yml` configured for pip, npm, cargo, github-actions.
- [ ] `CONTRIBUTING.md` references Conventional Commits and pre-commit setup.

## Recommended LLM brief (copy-pasteable prompt)

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
