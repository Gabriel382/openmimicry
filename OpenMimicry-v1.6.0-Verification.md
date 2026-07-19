# OpenMimicry v1.6.0 verification record

**Environment:** Linux release workspace, Python 3.12, Node 20+, pnpm 11.7  
**Date:** 2026-07-18

## Passed

- Python: 581 tests passed.
- Ruff: all active sources checked; 250 files formatted; zero findings.
- Pyright: zero errors and zero warnings.
- Import boundary checker: passed.
- Version consistency: passed across Python packages, JavaScript apps, Tauri,
  and Cargo metadata.
- Configuration: base plus all six shipped profiles validated under schema v2.
- Character packs: bundled packs and the v1.6 template validated; the VRM
  placeholder reports its documented speaking-frame fallback warning.
- Frontend: frozen pnpm install; 92 Vitest tests; TypeScript typecheck;
  production Vite build; external-echo TypeScript build.
- JavaScript dashboard syntax: passed.
- Production pnpm audit: no known vulnerabilities after pinning
  `react-router-dom` 6.30.4 and `ws` 8.21.0.
- Commercial Python lock: hash-required dry-run passed (69 packages).
- Commercial installed-closure license audit: passed with no denied, missing,
  or review records in the clean environment.
- Character template ZIP: contents listed, pack validated, SHA-256 recorded in
  the release manifest.

## Not run in this environment

- Rust/Tauri `fmt`, `clippy`, `test`, and native bundle (Cargo unavailable).
- Real microphone, speaker, wake-name, and multi-device audio acceptance.
- Chatterbox model download/hardware inference and ElevenLabs account calls.
- Windows/macOS native desktop and audio matrices.
- Live OpenRouter/Ollama/Hindsight provider calls.

These are explicit acceptance items in `docs/V1.6.0_ACCEPTANCE.md`; they are
not inferred from mocks or marked passed.

## Known non-product warning

The Python suite reports one upstream Starlette deprecation warning from
FastAPI's `TestClient` compatibility layer recommending the future `httpx2`
test client. It does not occur in the production server path. No dependency
jump was made solely to silence it.
