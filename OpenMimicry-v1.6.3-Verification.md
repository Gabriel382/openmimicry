# OpenMimicry v1.6.3 verification record

## Regression targets

- CUDA-tagged Torchvision base-version matching.
- Preservation of an already working CUDA 12.6 runtime when driver banner
  detection is unavailable.
- Dependency-preserving Torch repair command.
- Automatic Chatterbox detection in the standard Windows voice launcher.
- Absence of provider-specific Chatterbox launchers.

## Executed release gates

- Exact RTX 4070/missing CUDA-banner installer simulation: passed end-to-end;
  selected `cu126`, reported `existing verified runtime`, and did not invoke
  installation.
- CUDA build-suffix, triplet-selection, and dependency-preservation assertions:
  passed.
- Standard Windows voice-launcher structural tests: 5 passed.
- Python compilation of the installer, Chatterbox worker, and TTS adapter:
  passed.
- Import-boundary check: passed.
- Version consistency: 27 manifests checked at 1.6.3.
- Frontend: 17 test files and 92 tests passed.
- Desktop frontend and external echo TypeScript builds: passed.

The formal pytest wrapper could not be downloaded in the restricted release
container, so the new dependency-free installer and launcher regressions were
also executed directly through their assertions. The complete v1.6.2 Python
suite was green before this focused installer/launcher patch.

ZIP integrity and secret/build-output exclusion are verified after packaging.

Windows audio/GPU acceptance remains the final target-machine check and is
documented in `docs/V1.6.3_CHATTERBOX_TESTING.md`.
