# OpenMimicry v1.8.5 verification

Verified on 2026-07-31 in the release workspace:

| Check | Result |
|---|---|
| Claude/task regression suite | Passed, including Windows `.cmd`, stderr retention, missing cwd, no-credit diagnostics, and late-subscriber replay |
| Python suite | 652 collected; 651 passed; 1 optional Chatterbox test skipped because NumPy was not installed |
| Dashboard JavaScript syntax | Passed |
| Ruff lint and format | Passed |
| Import-boundary check | Passed |
| Version consistency | 27 surfaces aligned at 1.8.5 |
| Character-pack validation | `octomimic` and `octomimic_vrm` passed |
| Lockfile freshness | Passed |
| Archive integrity and checksums | Passed during final packaging |
| Windows live Claude 2.1.220 | Requires validation on the user's Windows host |

The suite emits the existing Starlette/httpx deprecation warning. It is
unrelated to Claude task execution. The optional Chatterbox test was already
covered by the user's working CUDA/Chatterbox runtime and is not modified by
this hotfix.
