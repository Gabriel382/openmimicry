# Changelog

All notable changes to OpenMimicry are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MX (tooling baseline):** workspace `pyproject.toml` with Ruff, pyright, pytest, coverage configuration. `.pre-commit-config.yaml` with ruff + commitlint. `.editorconfig`. `Makefile` targets `lint`, `format`, `typecheck`, `test`, `ci`, `check-imports`, `validate-packs`, `pre-commit-install`. Cross-platform `scripts/doctor.py` and `scripts/check_imports.py`. GitHub Actions: `ci.yml`, `release.yml`, `codeql.yml`. Dependabot grouped weekly updates.
- **Phase 0 (contract freeze):** runnable Protocols and Pydantic schemas under `packages/openmimicry-core/src/openmimicry/core/{contracts,schemas}/`. Sibling packages (`openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`, `openmimicry-tasks`) with stub `mocks.py` raising `NotImplementedError`. Contract test scaffolding in `tests/contract/` with parametrised fixtures.
- **M0 (`openmimicry-core` runtime):** `EventBus` (async fan-out with bounded queues), `RuntimeStore` (immutable snapshots), `AppConfig` loader with env-overlay + profile merge + Pydantic validation, `structlog`-based logging with bus tap, `Runtime` context manager, lifecycle helpers.
- **M1 (`openmimicry-llm`):** `MockLLMAdapter` (deterministic scripted mock, replaces Phase 0 stub), `LiteLLMAdapter` (lazy-imports LiteLLM; maps provider exceptions to typed `LLMTransportError`/`LLMAuthError`/`LLMToolCallError`), `LLMRouter` (primary + optional fallback with `RouterRetryPolicy`; never falls back on auth errors or after the primary has emitted chunks), tiny prompt registry (`openmimicry.llm.prompts.load`) with default `system_default.txt` and `system_personality.j2` Jinja2 templates. Both adapters register via the `openmimicry.contracts.llm` entry point and pass the un-skipped contract suite (`tests/contract/test_llm.py`). Optional install `pip install "openmimicry-llm[litellm]"` for the real provider stack.
- **Documentation:** `MAINTAINERS.md`, `CODE_OF_CONDUCT.md`, refreshed `CONTRIBUTING.md`, 15 GitHub issue templates spawning every module brief.

### Changed

- Project version moved from `0.1.0` → `0.2.0a0`.
- `Makefile`: added quality-floor and packaging targets while preserving the prototype's `backend`/`frontend`/`desktop` targets.
- `pyproject.toml`: switched profile names (`basic|voice|threejs|live3d|unity|agent|full|studio|dev`) to mirror the YAML profiles documented in [`docs/configuration.md`](docs/configuration.md) §6.
- **Supply-chain hardening:** the JS workspace moves from npm to **pnpm 11.x**. New root files: `.npmrc`, `pnpm-workspace.yaml`, root `package.json` with `packageManager: pnpm@11.0.0` and `engine-strict`. Three controls are enforced by `.npmrc`: `minimum-release-age=14` (refuse packages published in the last 14 days), `block-exotic-subdeps=true` (no git/tarball/file transitive deps), and `ignore-scripts=true` with an explicit `onlyBuiltDependencies` allowlist (postinstall scripts blocked by default). Full policy in [`SECURITY.md`](SECURITY.md). `Makefile` targets: `frontend-install`, `frontend-audit`, `frontend-approve-builds`. CI installs pnpm 11 via `pnpm/action-setup@v4` and runs `pnpm audit` on every PR. Dependabot restricted to non-major bumps so `minimum-release-age` can catch poisoned versions.

### Documentation

- Full module briefs under `docs/modules/`: Phase 0 + MX + M0..M9 + post-v0.2 (M10–M12).
- **M13 (vision, post-v0.2, optional):** new brief `docs/modules/M13_vision.md` for a camera-driven `MediaPipeVisionAdapter` + `GestureClassifier` registry that publishes `GestureDetected` events the avatar director maps to `AvatarDirective` overrides. Off by default, opt-in via `pip install openmimicry[vision]` and `vision.enabled: true`. Privacy-first: no upload, explicit consent dialog on first activation. `pyproject.toml` gains `vision` and `full-vision` extras; `Makefile` lists them under `make install PROFILE=…`. Implementation deferred — the contract surface (`VisionAdapter`, `GestureClassifier`, `HandLandmark`/`HandPose`/`GestureDetection`/`VisionConfig` schemas, three new `RuntimeEvent` variants) lands in a contracts-amendment PR before M13 begins.
- Architecture, adapter, event-flow, voice-mode, task-delegation, character-pack, desktop-overlay, configuration, testing-and-ci, and migration docs.

[Unreleased]: https://github.com/ghenrique/openmimicry/compare/v0.1.0...HEAD
