# OpenMimicry v1.9.1 verification record

Verification was performed on 2026-08-03 against the release source tree.
Network-backed model calls and physical audio playback were not required by the
automated suite.

## Results

| Check | Result |
|---|---|
| Python collection | 666 tests |
| Python suite | Pass, 666/666 |
| Pyright | Pass, 0 errors and 0 warnings |
| Ruff lint | Pass |
| Ruff formatting | Pass, 457 files |
| Python byte compilation | Pass |
| Import-boundary check | Pass |
| Version consistency | Pass, 27 declarations at 1.9.1 |
| Character-pack validation | Pass, Octomimic sprite2d and VRM |
| Dashboard JavaScript syntax | Pass |
| Frontend Vitest | Pass, 20 files and 100 tests |
| TypeScript check | Pass |
| Vite production build | Pass; large-chunk advisory only |

Rust/Tauri compilation was not rerun because Cargo is unavailable in the Linux
packaging environment. No Rust behavior changed; Rust edits are version metadata
only. The frontend consumed by Tauri passed tests, typecheck, and production
build.

## Regression coverage added

- Personality save transactionally updates wake identity.
- Legacy Portuguese values normalize to `pt-BR`.
- Language preparation runs in the background and commits atomically.
- Companion-bundled voice wins over a stale global same-ID profile.
- Full rotation range and legacy front-facing Three.js projection.
- Private character export/delete and protected bundled characters.
- Binary glTF/VRM embedded-animation discovery and alias suggestions.
- `Set an alarm to 17h!` deterministic routing.
- Personality identity and new companion/character controls in the dashboard.

## Packaging safeguards

The release archive excludes dependencies, virtual environments, caches, build
outputs, logs, credentials, local configuration, memory/task databases, creator
archives, restricted models, private imported characters, voice references, and
private companion profiles. Archive integrity and SHA-256 are checked after
creation.
