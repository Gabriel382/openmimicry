# OpenMimicry v1.8.3 verification record

Date: 2026-07-30

## Automated release gates

| Gate | Result |
| --- | --- |
| Python test suite | PASS — 641 passed, 1 skipped |
| Optional skip | Chatterbox worker import test; NumPy is absent from the minimal verification environment |
| Ruff lint and formatting | PASS — 431 files formatted |
| Pyright | PASS — 0 errors, 0 warnings |
| Import boundaries | PASS |
| Character pack validation | PASS — `octomimic`, `octomimic_vrm` |
| Frontend Vitest | PASS — 19 files, 98 tests |
| Frontend TypeScript | PASS |
| Frontend production build | PASS |
| Production VRM parser | PASS — real `GLTFLoader` + `VRMLoaderPlugin` |
| VRM deterministic regeneration | PASS — checked-in bytes equal generator output |
| pnpm production audit | PASS — no known vulnerabilities |
| Version consistency | PASS — 27 manifests/modules at 1.8.3 |

## Bundled asset verification

| Property | Verified value |
| --- | --- |
| Path | `characters/octomimic_vrm/octomimic.vrm` |
| Format | Binary glTF 2.0 with `VRMC_vrm` 1.0 |
| Size | 32,472 bytes |
| SHA-256 | `ebafe8f98cacbf65802150a080bde1fee1c473feb7d179cc5a8862f6f48b9b91` |
| VRM parsed | Yes |
| Humanoid map | Yes |
| Expression manager | Yes |
| Embedded clips | 10 |
| License | CC0-1.0 |

The parser regression verifies the lifecycle clips `idle`, `listening`,
`thinking`, `speaking`, `happy`, and `error`, plus `wave` and `celebrate`
gestures. A separate regression verifies that applying a new expression clears
the prior one.

## Environment-limited gates

The portable verification container has no Rust toolchain, GPU, microphone,
speaker, or Windows desktop session. Cargo/Tauri compilation, WebGL display,
live audio, CUDA, and Windows always-on-top behavior therefore remain
target-machine gates. The TypeScript production build and production VRM
parser both passed; no Rust source was changed.

## Release safety

The release excludes credentials, user configuration, raw/reference audio,
memory databases, task journals, logs, model caches, local characters,
personalities, and companion exports. Only the distributable built-in
characters are packaged.
