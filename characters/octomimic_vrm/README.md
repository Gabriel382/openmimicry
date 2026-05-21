# OctomimicVRM (M9 demo pack)

A minimal VRM pack used to exercise the Three.js avatar runtime end-to-end.

## What ships here

- `pack.yaml` — the pack manifest. Declares `kind: vrm` and points at
  `octomimic.vrm` via `metadata.asset`.
- `preview.png` — pack preview image used by the panel UI dropdown.

## Drop in a real `octomimic.vrm`

The binary `.vrm` is **not** checked in; this pack exists so the rest
of the M9 surface (`avatar.runtimes.threejs`, the wire schema, the
frontend runtime) is exercised in CI without dragging a VRM model into
git.

To enable the demo locally:

1. Place a VRM file at `characters/octomimic_vrm/octomimic.vrm`. Any
   public-domain or CC0-licensed VRM works — try the official
   [VRoid Hub](https://hub.vroid.com/) or the
   [Pixiv three-vrm samples](https://github.com/pixiv/three-vrm/tree/dev/packages/three-vrm/examples).
2. Add to your `app.yaml`:
   ```yaml
   avatar:
     runtime: threejs
     pack: octomimic_vrm
     runtimes:
       threejs:
         camera: { position: [0, 1.4, 1.6] }
         lighting: studio
   ```
3. Start the backend and the frontend. The overlay loads the VRM and
   plays the `idle` clip; emotions drive `expressionWeights`.

## Licensing reminder

If you ship a real VRM, declare its license in `pack.yaml` (replace
the placeholder `CC0-1.0`). VRM files often carry CC BY / personal-use
constraints — read the model's redistribution clause before committing.
