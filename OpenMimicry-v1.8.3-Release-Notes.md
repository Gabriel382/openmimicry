# OpenMimicry v1.8.3 release notes

Version 1.8.3 adds the missing ready-to-run 3D fixture for the Three.js
runtime.

## Bundled Octomimic VRM

`characters/octomimic_vrm/octomimic.vrm` is now a real VRM 1.0 binary rather
than a manifest that points to a missing file. Select runtime `threejs` and
pack `octomimic_vrm` in Settings to test it.

The model includes:

- a project-owned stylized 3D Octomimic mesh;
- the humanoid map required by VRM 1.0 loaders;
- VRM expression presets for the runtime's emotion projection;
- embedded `idle`, `listening`, `thinking`, `speaking`, `happy`, and `error`
  lifecycle clips;
- embedded `wave` and `celebrate` gesture clips.

No avatar download, model-conversion tool, Blender installation, or runtime
network request is required.

## Reproducible and redistributable

The model is created deterministically by:

```bash
python scripts/assets/generate_octomimic_vrm.py
```

The generator uses only the Python standard library, no randomness, and no
downloaded geometry or textures. The model and its animation data are
dedicated to the public domain under CC0-1.0. Embedded VRM metadata permits
commercial use, modification, and redistribution.

Third-party VRM models imported by users retain their own license terms.

## Runtime correction

Applying a new VRM expression now clears the previous expression weights
first. This prevents, for example, a happy material state remaining active
after the avatar moves to sad or neutral.

## Upgrade

Re-run the normal installation profile:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

Then choose `threejs` and `octomimic_vrm` in the dashboard. No voice model,
LLM provider, memory, or configuration migration is required.
