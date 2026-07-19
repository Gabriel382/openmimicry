# Reject and repair Chatterbox's non-callable Perth watermarker

## Release

OpenMimicry v1.6.4

## Observed failure

On Windows/Python 3.13, the runtime installer reported a healthy CUDA-enabled
Chatterbox 0.1.7 stack. Model preflight then failed in
`ChatterboxTurboTTS.__init__` because `perth.PerthImplicitWatermarker` was
`None`.

## Root cause

Perth 1.0.1 suppresses the neural watermarker's internal import failure and
exports a non-callable sentinel. The OpenMimicry runtime probe verified only
package/Torch versions, and Chatterbox calls the sentinel unconditionally.

## Resolution

- Verify the real Perth constructor in the runtime probe.
- Expose the suppressed direct-import traceback in diagnostics.
- On ordinary profile installation, replace only defective Perth with official
  commit `ce86c49d029f42272c1902eccb675556b9ed2330` using an immutable archive
  and `--no-deps`.
- Resolve/patch the real constructor at the isolated worker boundary.
- Fail closed instead of using a dummy/no-watermark fallback.
- Invalidate the old model-preflight marker for v1.6.4.

## Acceptance criteria

- The reported v1.6.3 environment initially fails `--check-only` with
  `perth_watermarker_callable: false`.
- Normal `openrouter-chatterbox` installation repairs Perth but does not invoke
  the Torch installer for an otherwise valid `2.6.0+cu118` triplet.
- The next check reports `passed: true` and
  `perth_watermarker_callable: true`.
- Chatterbox model preflight reaches the ready handshake.
- Three consecutive cloned-voice turns synthesize and leave the worker ready.
- A failed direct Perth import includes its original exception and never falls
  back to `DummyWatermarker`.

## Branch workflow

```bash
git switch dev
git pull --ff-only
git switch -c fix/v1.6.4-perth-watermarker

git add -A
git commit -m "fix(voice): repair Chatterbox Perth watermarker startup"

git switch dev
git merge --no-ff fix/v1.6.4-perth-watermarker
git tag -a v1.6.4 -m "OpenMimicry v1.6.4"
```
