# OpenMimicry v1.6.2 — Chatterbox Runtime Reliability

OpenMimicry v1.6.2 is a focused compatibility and installation release for
the optional local Chatterbox Turbo voice-cloning profile. It is based on
v1.6.1 and does not change configuration schema version 2 or the public adapter
contracts.

## Resolved failures

- Fixes Chatterbox 0.1.7 reference synthesis with NumPy 2.x, including Python
  3.13, without modifying the installed third-party package.
- Detects the CPU-only PyTorch wheel commonly resolved by pip on Windows and
  replaces it with the official version-matched CUDA wheel when supported.
- Prevents the Piper launcher and 30-second readiness deadline from being used
  accidentally for a dashboard-selected Chatterbox voice.
- Prevents the two-second HTTP health route from starting or cancelling a cold
  Chatterbox model worker.

## Installation

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-chatterbox.ps1
```

Linux or macOS:

```bash
./scripts/start-openrouter-chatterbox.sh
```

The launcher installs or repairs the `openrouter-chatterbox` profile, verifies
Torch/Torchaudio/Chatterbox imports, chooses a supported accelerator, performs
a one-time model download and prewarm, selects the correct profile and starts
Uvicorn without reload.

## Runtime selection

- NVIDIA: official Torch 2.6 `cu126`, `cu124`, or `cu118` wheel, selected from
  driver capability.
- Apple Silicon: platform-default Torch with MPS.
- No accelerator: CPU fallback, with materially slower synthesis.
- NVIDIA Blackwell: automatic mode fails closed because Chatterbox 0.1.7 pins
  Torch 2.6.0. It does not silently install a wheel without matching kernels.

Set `OPENMIMICRY_TORCH_CHANNEL` to `cpu`, `cu118`, `cu124`, or `cu126` only when
an explicit override is required. Set
`OPENMIMICRY_CHATTERBOX_PREFLIGHT=force` to rerun the model preflight.

## Compatibility isolation

The worker wraps Chatterbox's reference-audio loudness normalization and casts
its result back to float32. This contains the NumPy 2 promotion incompatibility
inside the disposable child process. It does not patch `.venv`, change global
NumPy promotion rules, or alter unrelated models.

## Upgrade

Apply the v1.6.2 source over v1.6.1, reinstall once with the dedicated
Chatterbox launcher, and continue using the reference and consent record
already stored in `config/user.yaml` and the private OpenMimicry data folder.
