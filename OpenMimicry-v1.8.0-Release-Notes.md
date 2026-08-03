# OpenMimicry v1.8.0 release notes

OpenMimicry v1.8 integrates production 3D rendering, local agent tasks,
selective internet research, and restart-safe task history while preserving the
existing companion, voice, personality, and optional-memory features.

## Highlights

- Transparent Three.js WebGL renderer for VRM and glTF/GLB, embedded
  `AnimationMixer` clips, cross-fades, expressions, VRM updates, optional VRMA,
  and configurable animation speed.
- Claude CLI task runtime defaults to the user's locally authenticated Claude
  subscription. Anthropic API mode remains explicit and optional.
- PicoClaw is an operational optional executable adapter.
- Project roots, tasks, update events, provider session ids, and completion
  notifications persist in SQLite.
- Dashboard task archive and non-disruptive notification center.
- OpenRouter web research is configurable per backend as off, deterministic
  automatic, or always. Automatic mode excludes greetings.
- Saved voice profiles and memory providers hot-refresh without restarting the
  backend; runtime readiness exposes the refresh.
- Last pack, avatar runtime, and named voice selection persist.
- 3D character ZIP validation and privacy-first ignore rules for local
  characters, voices, personalities, and companion exports.
- English, French, Spanish, and Portuguese locale configuration groundwork.
- Removed `react-router-dom` from the desktop frontend and its dependency tree.

## Install

```bash
make install PROFILE=integrated
OPENMIMICRY_PROFILE=integrated make backend
```

Windows:

```powershell
.\scripts\win\install.bat integrated
$env:OPENMIMICRY_PROFILE = "integrated"
.\scripts\win\backend.bat --no-reload
```

Run the desktop separately with `make desktop` or
`.\scripts\win\desktop.bat`.

Claude and PicoClaw are not installed by OpenMimicry. Install and authenticate
those optional executables independently. OpenRouter requires the user's own
environment or session token. Ollama remains local and optional.

## Compatibility

Configuration schema remains v2 and additions have defaults. Existing v1.6/v1.7
profiles continue to load. Task journal and notification tables are created
automatically. The frontend requires a lockfile refresh because
`@pixiv/three-vrm-animation` was added and `react-router-dom` was removed.

## Known verification boundary

The portable source was validated with Python and browser tests in the build
environment. Rust/Cargo and real audio/GPU/VRM/Claude/Pico providers require
target-machine acceptance because those toolchains and user assets are not
bundled.

