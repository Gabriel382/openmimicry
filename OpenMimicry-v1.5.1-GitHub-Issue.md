# v1.5.1 — fall back when auto-detected CUDA is incomplete

## Problem

CTranslate2 may report an NVIDIA device even when required CUDA 12 runtime DLLs
are absent. The v1.5.0 preflight then selected CUDA and failed on
`cublas64_12.dll` instead of using the supported CPU/INT8 lane.

## Acceptance criteria

- [x] Treat CUDA device enumeration as a hint, not a successful runtime probe.
- [x] Retry model construction on CPU/INT8 when auto-selected CUDA fails.
- [x] Retry on CPU/INT8 when CUDA fails lazily during first inference.
- [x] Use identical selection logic in the preflight and backend STT worker.
- [x] Report the actual device, compute type, and fallback reason.
- [x] Keep explicit `device: cuda` strict.
- [x] Add model-load, lazy-inference, and strict-CUDA regression tests.
- [ ] Complete the Windows matrix in `docs/V1.5.1_WINDOWS_TESTING.md`.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only
git switch -c fix/v1.5.1-cuda-auto-fallback
```

After Windows acceptance:

```bash
git switch dev
git merge --no-ff fix/v1.5.1-cuda-auto-fallback
git tag -a v1.5.1 -m "OpenMimicry v1.5.1"
git push origin dev v1.5.1
```

This is a patch release because it corrects `device: auto` without changing
the public configuration schema or adapter contracts.
