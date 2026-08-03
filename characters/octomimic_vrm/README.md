# OctomimicVRM

A compact, animated VRM 1.0 pack used to exercise the Three.js avatar
runtime end-to-end. It is bundled and ready to select; no model download is
required.

## What ships here

- `pack.yaml` — the pack manifest. Declares `kind: vrm` and points at
  `octomimic.vrm` via `metadata.asset`.
- `octomimic.vrm` — a real VRM 1.0 binary with project-owned geometry.
- `preview.png` — pack preview image used by the panel UI dropdown.

## Test it

1. Select the `threejs` runtime and `octomimic_vrm` character pack in
   Settings, or configure:
   ```yaml
   avatar:
     runtime: threejs
     pack: octomimic_vrm
     runtimes:
       threejs:
         camera: { position: [0, 1.4, 1.6] }
         lighting: studio
   ```
2. Start the backend and desktop. The overlay loads the bundled model.
3. Send prompts or use voice to exercise `listening`, `thinking`,
   `speaking`, emotion, and gesture transitions.

Embedded clips: `idle`, `listening`, `thinking`, `speaking`, `happy`,
`error`, `wave`, `gesture_wave`, `celebrate`, and `gesture_celebrate`.

## Regenerate it

The checked-in binary is deterministic:

```bash
python scripts/assets/generate_octomimic_vrm.py
```

The generator uses only the Python standard library and does not download
assets.

## License

The model, geometry, animation data, and pack metadata are dedicated to the
public domain under CC0-1.0. The VRM metadata permits commercial use,
redistribution, and modification. This permissive fixture does not change
the licensing requirements for VRM files users import themselves.
