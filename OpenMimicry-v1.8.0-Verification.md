# OpenMimicry v1.8.0 verification record

Date: 2026-07-30  
Artifact: `OpenMimicry-v1.8.0-integrated-source.zip`

## Automated release gates

| Gate | Result |
| --- | --- |
| Python test suite | PASS — 630 passed, 1 skipped |
| Optional skip | Chatterbox worker import test; NumPy is intentionally absent from the minimal verification environment |
| Ruff lint | PASS |
| Ruff formatting | PASS — 416 files checked |
| Pyright | PASS — 0 errors, 0 warnings |
| Import-boundary check | PASS |
| Version-consistency check | PASS — 27 manifests/modules at 1.8.0 |
| Python compileall | PASS |
| Frontend Vitest | PASS — 17 files, 94 tests |
| Frontend TypeScript | PASS |
| pnpm production audit | PASS — no known vulnerabilities |
| ZIP integrity | Recorded after packaging in the external SHA-256 file |

The Python typecheck used the verification interpreter explicitly because the
release workspace intentionally contains no `.venv`.

## Target-machine gates

The following require tooling, credentials, licensed assets, or hardware that
is not bundled in the portable source:

- `cargo fmt --check`, `cargo clippy -- -D warnings`, and `cargo test`;
- Tauri overlay behavior on Windows, macOS, and Linux compositors;
- VRM/VRMA/glTF/GLB rendering with user-supplied models;
- microphone, speaker, CUDA, Piper, and Chatterbox smoke tests;
- authenticated Claude CLI subscription/API and optional PicoClaw runs;
- live OpenRouter/Ollama and web-research provider calls.

These are explicit acceptance steps in `docs/V1.8.0_ACCEPTANCE.md`, not silent
claims made by the portable build.

## Release safety

- No provider token or local API credential is included.
- No raw audio, voice reference, memory database, task journal, log, model
  cache, or user configuration is included.
- Locally imported characters and companion exports are excluded.
- Only the redistributable built-in packs `mimic_blue`, `octomimic`, and
  `octomimic_vrm` are included.
- Optional providers and imported assets retain their own license and service
  terms.
