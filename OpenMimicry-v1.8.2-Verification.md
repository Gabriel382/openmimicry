# OpenMimicry v1.8.2 verification record

Date: 2026-07-30

## Automated release gates

| Gate | Result |
| --- | --- |
| Python test suite | PASS — 638 passed, 1 skipped |
| Optional skip | Chatterbox worker import test; NumPy is absent from the minimal verification environment |
| Hung LiteLLM stream regression | PASS |
| Failed-turn lease recovery regression | PASS |
| Ruff lint | PASS |
| Pyright | PASS — 0 errors, 0 warnings |
| Frontend Vitest | PASS — 18 files, 96 tests |
| Thinking/error presentation regressions | PASS |
| Frontend TypeScript | PASS |
| Version consistency | PASS — 27 manifests/modules at 1.8.2 |

## Target-machine gates

Live OpenRouter behavior, Chatterbox/Piper playback, microphone capture, CUDA,
and Windows Tauri always-on-top behavior require the user's hardware,
credentials, and installed providers. They are not claimed by the portable
verification environment.

## Release safety

The release excludes credentials, user configuration, raw/reference audio,
memory databases, task journals, logs, model caches, local characters,
personalities, and companion exports. Only the distributable built-in
characters are packaged.
