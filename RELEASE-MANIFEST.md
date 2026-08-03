# OpenMimicry v1.8.5 release manifest

## Contents

- Complete MIT-licensed OpenMimicry v1.8.5 source.
- All integrated v1.8.0 features: Three.js/VRM, local Claude CLI and PicoClaw
  task adapters, durable tasks, selective research, voice profiles, optional
  memory, and private companion profiles.
- The v1.8.1 same-schema compatibility fix for the retired Boolean
  `web_search` key.
- White avatar thinking balloon with red reserved for actual failures.
- A whole-stream LLM deadline and terminal failure propagation that always
  releases the active turn.
- A bundled, ready-to-run CC0 VRM 1.0 Octomimic with lifecycle, emotion, and
  gesture animation clips.
- Deterministic VRM generation and production-loader regressions.
- Atomic pack/runtime compatibility, startup repair, and saved per-pack 3D
  framing/animation speed.
- Stable Three.js asset/canvas lifecycle and 13–19-keyframe bundled clips.
- Toolbar task notifications and the local Claude subscription quickstart.
- Reliable Windows Claude executable discovery and `.cmd` launcher support.
- Visible, no-credit Claude version/authentication/working-directory
  diagnostics.
- Durable stderr/error details plus late-subscriber replay for fast failures.
- Release notes, migration notes, verification record, and checksums.

## Artifacts

- `OpenMimicry-v1.8.5-claude-task-runtime-hotfix-source.zip`
- `OpenMimicry-v1.8.5-claude-task-runtime-hotfix-docs.zip`
- `OpenMimicry-v1.8.5-SHA256SUMS.txt`

The source archive excludes environments, dependencies, build outputs, caches,
credentials, databases, logs, raw/reference audio, local characters,
personalities, task journals, memory stores, and companion exports.

Claude CLI, PicoClaw, cloud services, provider credentials, imported models,
and user assets are not bundled and retain independent terms.
