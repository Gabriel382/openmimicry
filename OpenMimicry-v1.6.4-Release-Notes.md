# OpenMimicry v1.6.4 — Perth Watermark Startup Repair

OpenMimicry v1.6.4 corrects the Chatterbox Turbo startup failure reported on
Windows/Python 3.13 with an RTX 4070 Laptop GPU:

```text
TypeError: 'NoneType' object is not callable
self.watermarker = perth.PerthImplicitWatermarker()
```

## Root cause

The published `resemble-perth` 1.0.1 package catches an internal `ImportError`
while importing its neural watermarker and publishes
`PerthImplicitWatermarker = None`. Chatterbox 0.1.7 later calls that value
without validating it, hiding the original failure behind a `NoneType` error.
The v1.6.3 installer checked package and Torch versions but did not verify this
constructor, so it incorrectly reported `passed: true` before model preflight.

## Permanent repair

- The ordinary Chatterbox runtime check now records Perth's version, import
  origin, and `perth_watermarker_callable` result.
- A non-callable constructor makes `--check-only` fail and triggers the normal
  `openrouter-chatterbox` profile repair.
- Repair installs only the official MIT Perth repository at immutable commit
  `ce86c49d029f42272c1902eccb675556b9ed2330`. It uses `--no-deps`, preserving
  the verified Torch/Torchaudio/Torchvision/CUDA/NumPy environment.
- Worker startup resolves the implementation directly before Chatterbox loads.
  If it still fails, diagnostics contain the underlying import exception.
- OpenMimicry never substitutes Perth's dummy watermarker; generated
  Chatterbox audio retains the upstream safety watermark.

## Upgrade and run

No provider-specific launcher or manual `.venv` edit is required. Replace the
repository files with v1.6.4, preserve `.env` and `config/user.yaml`, then run:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The first run may download/build the pinned Perth source and load the cached
Chatterbox model. A valid report contains:

```json
{
  "passed": true,
  "after": {
    "perth_watermarker_callable": true
  }
}
```

The existing CUDA 11.8 installation on the reported RTX 4070 is valid and is
not replaced merely because `nvidia-smi` omits its driver CUDA banner.
