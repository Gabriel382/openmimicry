# OpenMimicry v1.9.2 release notes

OpenMimicry v1.9.2 is a focused reliability release for passive listening,
private custom VRM characters, and local Chatterbox synthesis. It is
configuration-compatible with v1.9.1.

## Wake listening now stays off

TTS temporarily pauses passive listening to avoid hearing the avatar's own
speaker output. Previously, an in-flight TTS turn retained a stale resume token;
if wake listening was switched off before playback ended, that token could
restart the microphone afterward.

The controller now tracks the user's requested listening state separately from
the temporary recorder state. Disabling wake or continuous mode invalidates all
later resume attempts. The backend also rejects a recorder's final queued
transcript if its input mode has already been disabled.

## One generic custom VRM importer

Creator-specific Torikinoko and MINIUS presets have been removed. The dashboard
now has one **Import a custom VRM character locally** form requiring a private
pack ID, display name, author/owner, license terms, and a ZIP containing exactly
one `.vrm`; a credits URL is optional. Only that model is copied to the private
user data directory. Imported assets are not added to Git or release archives.

All unsaved Three.js models and newly imported VRMs default to Y rotation 180°.
An explicit transform saved for a character remains authoritative.

## Clips and expressions are reported honestly

Skeletal clips and facial expressions are different VRM features. The
dashboard now discovers and reports both independently. VRM 0 expression names
are translated to their Three.js runtime presets (`Joy` to `happy`, `Sorrow` to
`sad`, and so on), while custom expressions are resolved case-insensitively.

Direct inspection of the supplied archives found:

- MINIUS: zero embedded skeletal animation clips and 17 facial expressions;
- Torikinoko: zero embedded skeletal animation clips and 24 facial/shape
  expressions.

These models therefore cannot expose named skeletal clips that are absent from
their VRM files. OpenMimicry now supplies stable procedural idle, listening,
thinking, speaking, happy, and error motion at renderer frame rate for clipless
VRMs. Motion is recomputed from a fixed load-time basis and does not accumulate
position or rotation between messages.

## Chatterbox tool replies recover cleanly

The isolated worker normalizes tool-result text, removes invisible control
characters, and wraps the Chatterbox Turbo tokenizer with a narrow compatibility
retry: only the exact scalar `TextEncodeInput` TypeError is retried as a
one-item batch. Any failed or interrupted synthesis discards the worker, so the
next reply starts from a clean model process instead of reusing partial state.

No specialized installation or launcher was introduced. Use the same project
installation profile and `start-openrouter-voice.ps1` command as v1.9.1.

## Boundaries

- Imported third-party characters retain their original terms and are never
  part of OpenMimicry's MIT grant.
- Named skeletal animation mapping still requires clips embedded in the model
  or separately supplied VRMA support.
- Physical microphone, speaker, CUDA, and cloned-voice behavior must ultimately
  be exercised on the target machine.
