# OpenMimicry v1.6.3 — Unified Voice Setup

OpenMimicry v1.6.3 is a corrective release over v1.6.2. It removes the need
for a dedicated Chatterbox launcher and fixes CUDA runtime verification on the
Windows configuration reported by an RTX 4070 Laptop GPU.

## Corrected failures

- CUDA-tagged versions such as `torchvision 0.21.0+cu126` now satisfy the
  version-matched Torch 2.6 runtime check.
- If `nvidia-smi` omits a parseable CUDA banner, OpenMimicry reuses a complete
  installed CUDA runtime that imports successfully and sees the GPU. It no
  longer guesses CUDA 11.8 and replaces a working CUDA 12.6 installation.
- A necessary accelerator repair reinstalls only Torch, Torchvision, and
  Torchaudio. It does not force-reinstall NumPy or unrelated dependencies.
- The post-install verification uses the actual selected/reused channel.

## One Windows voice launcher

Chatterbox is installed through the ordinary profile command:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
```

Piper and Chatterbox then use the same execution command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The launcher reads the TTS adapter saved by the dashboard. It automatically
selects `openrouter-voice` for Piper or `openrouter-chatterbox` for local voice
cloning, validates the matching dependencies, performs the appropriate
preflight, and starts the ordinary backend without reload.

The separate `start-openrouter-chatterbox.ps1` and
`start-openrouter-chatterbox.sh` entry points have been removed.

## Linux and macOS

The existing profile/backend mechanism remains the canonical path:

```bash
make install PROFILE=openrouter-chatterbox
OPENMIMICRY_PROFILE=openrouter-chatterbox make backend
```

No configuration schema or adapter contract changed.
