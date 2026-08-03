# OpenMimicry v1.6.2 verification record

## Automated results

- Full Python test suite: passed; the NumPy-dependent worker test was skipped
  only in the minimal test environment and was run separately below.
- Chatterbox worker test under NumPy 2.3.5: passed, including exact float32
  reference conditioning and idempotent compatibility installation.
- Chatterbox runtime selection and version-triplet tests: 8 passed.
- Frontend: 17 test files and 92 tests passed.
- TypeScript production builds: desktop frontend and external echo passed.
- Ruff lint and formatting checks: passed.
- Pyright: passed.
- Import-boundary validation: passed.
- Version consistency: 27 manifests checked, all at 1.6.2.
- POSIX launcher shell syntax: passed.
- PowerShell launcher behavior is covered by unit/static tests.

## Packaging checks

The release archive excludes virtual environments, dependencies, frontend and
Rust build outputs, caches, bytecode, logs, databases, and user configuration.
It retains only source, manifests/locks, public examples, tests, and release
documentation.

## Hardware acceptance remaining

The container cannot execute Windows PowerShell 5.1, Windows audio playback,
an NVIDIA CUDA worker, or a real cloned-voice model. Before tagging, run the
three-turn Windows acceptance sequence documented in
`docs/V1.6.2_CHATTERBOX_TESTING.md` on the target machine. This is the only
remaining platform acceptance step; it is intentionally not represented as an
automated pass.
