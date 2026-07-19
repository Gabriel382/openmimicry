# Unify Chatterbox setup and preserve verified CUDA runtimes

## Release

OpenMimicry v1.6.3

## Observed failure

On an RTX 4070 Laptop GPU, `nvidia-smi` returned a GPU and compute capability
but no parseable driver CUDA banner. OpenMimicry guessed `cu118` and replaced a
working `2.6.0+cu126` triplet. Verification then rejected the newly installed
runtime because it compared `torchvision 0.21.0+cu118` to the bare version
`0.21.0`.

The setup also required a Chatterbox-only PowerShell launcher, inconsistent
with the other voice providers.

## Resolution

- Accept official local build suffixes while still enforcing the exact base
  Torch/Torchvision/Torchaudio versions.
- Prefer an already verified CUDA triplet over a fallback guess.
- Use dependency-preserving `--no-deps` Torch repairs.
- Detect Chatterbox from `config/user.yaml` in
  `scripts/win/start-openrouter-voice.ps1`.
- Remove the provider-specific Chatterbox launchers.

## Acceptance criteria

- A valid `2.6.0+cu126` / `0.21.0+cu126` runtime passes when the CUDA banner is
  missing and no package download occurs.
- A valid `cu118`, `cu124`, or `cu126` runtime passes its post-install check.
- An actual mismatch repairs only the Torch triplet.
- Piper and dashboard-selected Chatterbox both start through
  `start-openrouter-voice.ps1`.
- Three consecutive cloned-voice turns complete on Windows.

## Branch workflow

```bash
git switch dev
git pull --ff-only
git switch -c fix/v1.6.3-unified-chatterbox

git add -A
git commit -m "fix(voice): unify Chatterbox setup and preserve CUDA runtime"

git switch dev
git merge --no-ff fix/v1.6.3-unified-chatterbox
git tag -a v1.6.3 -m "OpenMimicry v1.6.3"
```
