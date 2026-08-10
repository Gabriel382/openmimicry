# OpenMimicry v1.9.2 verification record

Verification was performed on 2026-08-03 against the release source tree.

## Results

| Check | Result |
|---|---|
| Python suite | Pass, 670/670 |
| Ruff lint | Pass |
| Ruff formatting | Pass, 467 files |
| Pyright | Pass, 0 errors and 0 warnings |
| Import-boundary check | Pass |
| Version consistency | Pass, 27 declarations at 1.9.2 |
| Character-pack validation | Pass, Octomimic Sprite2D and VRM |
| Dashboard JavaScript syntax | Pass |
| Frontend Vitest | Pass, 20 files and 102 tests |
| TypeScript / Vite build | Pass; large-chunk advisory only |

The supplied MINIUS and Torikinoko archives were also passed through the real
generic importer in a temporary private directory. The inspector reported
zero/17 and zero/24 skeletal clips/facial expressions respectively.

Cargo is unavailable in the Linux packaging environment, so Rust/Tauri was not
compiled. Rust changes are version metadata only; the frontend consumed by
Tauri passed its complete test, typecheck, and production-build gates. Physical
Windows microphone, CUDA, speaker, and Chatterbox playback remain target-machine
acceptance checks.

## Regression coverage

- wake-off during TTS invalidates the stale post-playback resume;
- generic VRM imports persist the 180° default rotation;
- glTF skeletal clips and VRM 0/1 facial expressions are discovered separately;
- actual MINIUS and Torikinoko archives report zero clips and 17/24 expressions;
- clipless VRM procedural movement remains bounded and non-accumulating;
- the exact Chatterbox scalar `TextEncodeInput` failure retries as a batch;
- hidden tool-result control characters are removed before synthesis;
- creator preset controls/names are absent from the active dashboard.

## Packaging safeguards

The release archive excludes environments, dependencies, caches, build output,
logs, credentials, local configuration, databases, private imported characters,
uploaded archives, voice references, and private companion profiles.
