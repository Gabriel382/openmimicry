# Testing, tooling, and CI/CD

Portfolio-grade open source is read more than it is run. Every choice in this document is biased toward "a stranger can look at the repo for two minutes and trust it."

## 1. Test layers

```text
tests/
  unit/
    core/               schemas, event bus, config validation, runtime store
    avatar/             pack loader, validator, director state machine, orchestrator
    voice/              SpeechController, mock STT/TTS, mode toggles
    llm/                LLMRouter, prompt registry, mock LLM
    tasks/              router, per-adapter parsers, capability matching
  contract/             parametrised contract suites — one per adapter family
    test_llm_contract.py            LLMAdapter
    test_stt_contract.py            STTAdapter
    test_tts_contract.py            TTSAdapter
    test_task_runtime_contract.py   TaskRuntimeAdapter
    test_avatar_runtime_contract.py AvatarRuntimeAdapter (mock, sprite2d, threejs, unity-mock)
  integration/
    test_flows.py             text/PTT/wake/task end-to-end on the bus
    test_voice_modes.py       barge-in, interrupt, mode swaps
    test_task_routing.py
    test_config_reload.py
    test_runtime_swap.py      AvatarOrchestrator.swap_runtime preserves state
  e2e/
    test_ws_projection.py     FastAPI TestClient + mock adapters
    playwright/               Optional: panel route smoke tests, Sprite2D + Three.js renders
  fixtures/
    packs/                    tiny synthetic packs for tests (sprite2d + glTF stub)
    configs/                  minimal configs for each profile
    directives/               canonical AvatarDirective samples for renderer tests
```

Three non-negotiable rules:

1. No test depends on real audio hardware or a real LLM provider. CI runs entirely on mocks.
2. Every public adapter contract has at least one "contract test" — a parametrised pytest that any new adapter can run against itself by registering with `pytest.mark.contract`. The five contract suites are `LLMAdapter`, `STTAdapter`, `TTSAdapter`, `TaskRuntimeAdapter`, `AvatarRuntimeAdapter`.
3. New modalities are first-class citizens of CI. Adding `Sprite2DAvatarAdapter`, `ThreeJSAvatarAdapter`, or `UnityAvatarAdapter` means registering with the `AvatarRuntimeAdapter` contract suite *and* contributing per-runtime Vitest/Rust tests under `apps/desktop/`. A modality that can't pass the contract test does not ship.

## 2. Tooling

| Tool | Scope | Config |
|---|---|---|
| `ruff` | lint + format | `pyproject.toml` `[tool.ruff]` |
| `pyright` | type-check | `pyrightconfig.json`, strict on core, avatar (orchestrator + base + sprite2d), llm |
| `pytest` | tests | `pyproject.toml` `[tool.pytest.ini_options]` |
| `pytest-cov` | coverage | fail under 80% on core, 60% on others |
| `pytest-xdist` | parallel | `-n auto` |
| `mypy` (optional) | secondary check | only when pyright disagrees |
| `pre-commit` | local gate | runs ruff + a tiny subset of pytest |
| `uv` | dependency manager | one lockfile per package, one workspace at root |
| Frontend: `eslint`, `prettier`, `vitest`, `tsc --noEmit` |

The Rust side (`src-tauri`) uses `cargo fmt`, `cargo clippy -- -D warnings`, and `cargo test`.

`make test`, `make lint`, `make typecheck`, `make ci` run these locally so contributors don't have to remember the incantations.

## 3. Conventional Commits + auto-changelog

- Every commit on `main` must be a Conventional Commit (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `build:`).
- A `commit-msg` hook (via `commitlint`) enforces this locally.
- `release-please` (or `git-cliff`) generates `CHANGELOG.md` from the commit history on every tag.

## 4. GitHub Actions

Five workflows under `.github/workflows/`:

```text
ci.yml         on PR + push to main
release.yml    on tag vX.Y.Z
docs.yml       on push to main, publishes /docs to GitHub Pages
pack-lint.yml  validates character packs and example configs
codeql.yml     security scanning
```

Sketch of `ci.yml`:

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
jobs:
  python:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        py: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-packages
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pyright
      - run: uv run pytest -n auto --cov --cov-fail-under=70
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: apps/desktop/frontend/package-lock.json }
      - run: npm ci
        working-directory: apps/desktop/frontend
      - run: npm run lint
        working-directory: apps/desktop/frontend
      - run: npm run typecheck
        working-directory: apps/desktop/frontend
      - run: npm test -- --run
        working-directory: apps/desktop/frontend
  rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo fmt --check
        working-directory: apps/desktop/src-tauri
      - run: cargo clippy -- -D warnings
        working-directory: apps/desktop/src-tauri
      - run: cargo test
        working-directory: apps/desktop/src-tauri
```

## 5. Releases

- **Versioning.** SemVer. While we are on `0.x`, adapter contracts can move; we document every move in `CHANGELOG.md`. `1.0.0` is reserved for "the four adapter contracts are stable."
- **Tags.** Trigger releases via `git tag -a vX.Y.Z -m '...' && git push --tags`.
- **release.yml** does:
  1. Generate `CHANGELOG.md` entries from Conventional Commits since the previous tag.
  2. Build Python wheels for `openmimicry-core`, `openmimicry-avatar`, `openmimicry-voice`, `openmimicry-llm`, `openmimicry-tasks` (sdist + wheel via `uv build`).
  3. Build Tauri bundles via `tauri-action` for Windows (`.msi`, `.exe`) and Linux (`.AppImage`, `.deb`).
  4. Compute SHA256 sums; sign with `sigstore` (optional but worth it for portfolio polish).
  5. Create a GitHub Release with the changelog as the description and the artifacts attached.
- **Pre-releases.** Tags like `v0.2.0-rc.1` go to a "Pre-release" GitHub Release and are not pinned in docs.

## 6. Docs site

`docs.yml` builds and deploys `/docs` to GitHub Pages via MkDocs Material (or `mdBook` if we prefer Rust-side). The architecture, adapter, and event-flow docs are the primary content. The site is linked from the README header.

## 7. Coverage and badges

The README header gets these badges, in order:

- CI status (`ci.yml`).
- Latest release.
- Python versions supported.
- License.
- Coverage (Codecov).
- DOI (Zenodo) once `1.0` ships.

The point of badges is to make the project legible at a glance, not to gamify them. We avoid the "30 badges, all green, none meaningful" trap.

## 8. Security workflow

- `SECURITY.md` lists how to report a vulnerability and the response timeline.
- `codeql.yml` runs the default CodeQL config on Python and JavaScript.
- Dependabot is on for `pip`, `npm`, and `cargo`. Grouped weekly PRs reduce noise.
- The `local_shell_adapter` and any path-handling code get extra unit tests for path traversal.

## 9. Reproducibility

- All commands documented in `README.md` are runnable from a fresh clone with `make doctor && make install PROFILE=basic && make dev`.
- `uv.lock`, `apps/desktop/frontend/package-lock.json`, and `apps/desktop/src-tauri/Cargo.lock` are committed.
- A `devcontainer.json` (optional) gives recruiters a one-click "open in Codespaces" path.
