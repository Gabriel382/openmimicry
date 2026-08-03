# OpenMimicry v1.8.4 release notes

OpenMimicry v1.8.4 is a focused avatar-persistence, Three.js lifecycle, and
task-notification release.

## User-visible changes

- Selecting a character automatically selects its compatible runtime from
  `pack.yaml`. VRM/glTF characters use Three.js; Sprite2D packs use Sprite2D.
- Character and runtime are persisted as one pair. A stale incompatible pair
  from v1.8.3 is repaired on startup.
- The 3D dashboard now exposes per-character auto-fit, position, rotation,
  scale, fitted height, vertical center, and animation speed. Changes preview
  without a backend restart and persist in `config/user.yaml`.
- The bundled CC0 Octomimic VRM now contains 13–19 keyframes for each embedded
  idle, listening, thinking, speaking, emotion, and gesture clip.
- The avatar toolbar has a bell with an unread task-notification badge.
- `docs/TASKS_AND_CLAUDE.md` explains the current task lifecycle, project
  folders, and Claude Team/subscription mode without an API key.

## Correctness fixes

- Three.js asset loading is keyed by asset identity and a stable animation
  manifest, not by each newly allocated directive object.
- Replaced renderer canvases are removed before a new canvas is attached.
- 3D transforms are absolute relative to a load-time basis, preventing
  per-message drift.
- A candidate character/runtime loads successfully before it replaces the live
  runtime.
- Startup resolves the selected character's actual pack path instead of
  reusing a default runtime `pack_path`.

## Compatibility

- Configuration schema remains version 2.
- Existing Sprite2D packs and companion/voice profiles remain compatible.
- No new mandatory cloud service or API key was added.
- Existing `POST /runtime/swap` callers receive a conflict response for an
  incompatible runtime and should use `POST /pack/swap`.

