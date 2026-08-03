# Fix Chatterbox reference synthesis and make its runtime installation recoverable

## Release

OpenMimicry v1.6.2

## Problem

Chatterbox 0.1.7 can fail on reference-voice synthesis under NumPy 2 with
`expected scalar type Double but found Float`. On Windows, a normal pip
resolution may also leave Chatterbox on CPU-only PyTorch even when a supported
NVIDIA GPU is present. Cold model startup can exceed the former readiness
deadline, while an HTTP health probe could inadvertently start and then cancel
the worker.

## Scope

- Contain the NumPy 2 reference-audio dtype workaround in OpenMimicry's
  disposable Chatterbox worker; never edit `site-packages`.
- Install and verify the exact PyTorch 2.6.0, Torchvision 0.21.0, and
  Torchaudio 2.6.0 triplet from an official PyTorch channel.
- Auto-select CPU, Apple MPS, or a supported NVIDIA CUDA wheel and fail with an
  actionable message for unsupported hardware/runtime combinations.
- Add dedicated Windows and POSIX Chatterbox launchers with a bounded model
  preflight and a 180-second cold-start deadline.
- Keep health checks observational: they must not cold-start the model.
- Preserve text fallback and discard an incomplete or crashed worker so the
  next attempt can recover.

## Acceptance criteria

- A consented WAV or MP3 reference synthesizes at least three sequential turns
  with NumPy 2.x, and every turn reaches a terminal TTS state.
- Worker diagnostics report device, Torch/CUDA, NumPy, and compatibility state.
- CPU-only Torch on a supported NVIDIA machine is detected and repaired.
- A mismatched or initially unimportable Torch triplet is repaired by the
  installer rather than leaving a poisoned environment.
- No third-party installed source file is modified.
- `/health` does not create a Chatterbox process.
- Existing Piper, ElevenLabs, and text-only profiles remain unchanged.

## Branch and merge workflow

```bash
git switch dev
git pull --ff-only
git switch -c fix/v1.6.2-chatterbox-runtime

# Apply and verify the v1.6.2 source.
git add -A
git commit -m "fix(voice): harden Chatterbox runtime and NumPy 2 synthesis"

git switch dev
git merge --no-ff fix/v1.6.2-chatterbox-runtime
git tag -a v1.6.2 -m "OpenMimicry v1.6.2"
```

Run the Windows acceptance path in `docs/V1.6.2_CHATTERBOX_TESTING.md` before
pushing the tag.
