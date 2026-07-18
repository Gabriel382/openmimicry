# OpenMimicry v1.5.1 release notes

OpenMimicry v1.5.1 fixes automatic hardware selection for the isolated
Faster-Whisper runtime on Windows systems where an NVIDIA device is visible but
the matching CUDA libraries are incomplete.

## Fixed

- `device: auto` now proves CUDA by loading the model and completing inference.
- A failed CUDA load or first inference, including missing
  `cublas64_12.dll`, automatically retries on CPU with INT8 compute.
- The preflight JSON reports the device and compute type that actually passed,
  plus the original fallback reason.
- The backend STT worker uses the same fallback policy as the preflight.
- `device: cuda` remains strict and preserves the original CUDA error.

The Hugging Face Windows symlink-cache warning is harmless and does not require
Administrator privileges or Developer Mode. It only affects cache disk usage.

## Upgrade

Replace the v1.5.0 source with v1.5.1 and run:

```powershell
.\scripts\win\install.bat openrouter-voice
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The v1.5.1 launcher uses a new preflight marker, so it automatically reruns the
real voice validation once after upgrading.
