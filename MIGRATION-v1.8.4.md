# Migrating to OpenMimicry v1.8.4

1. Stop the backend and desktop.
2. Replace the source tree, preserving `.env`, `config/user.yaml`, and
   `~/.openmimicry`.
3. Run the normal installer for the profile you use.
4. Start the backend, then the desktop.
5. Open Settings and select the desired character once.

On the first v1.8.4 launch, OpenMimicry examines the selected pack kind. If an
older user overlay contains an incompatible pair such as:

```yaml
avatar:
  pack: octomimic_vrm
  runtime: sprite2d
```

the runtime is repaired to `threejs` and the compatible pair is persisted.

3D framing defaults to automatic fit. Existing packs require no manifest
change. Optional per-pack settings are stored as:

```yaml
avatar:
  animation_speed: 1.0
  runtimes:
    threejs:
      transforms:
        octomimic_vrm:
          position: [0.0, 0.0, 0.0]
          rotation: [0.0, 0.0, 0.0]
          scale: 1.0
          auto_fit: true
          target_height: 0.72
          target_y: 1.3
```

Do not hand-edit this section unless the backend is stopped. The dashboard
validates and writes the same values atomically.

