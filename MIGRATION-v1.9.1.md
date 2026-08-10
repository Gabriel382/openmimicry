# Migrating from OpenMimicry v1.9.0 to v1.9.1

## Compatibility

v1.9.1 does not require a destructive data migration. Existing configuration,
memory, task journal, voice profiles, imported characters, and companion
profiles remain readable. Back up `~/.openmimicry` before any upgrade.

## Identity migration

The authoritative assistant identity is now:

- `personality.name`
- `personality.aliases`

The Voice page no longer edits wake names separately. Applying Personality or a
companion rewrites the live wake set from those two fields. Put every phrase
that should wake the companion in Personality aliases; do not duplicate the
assistant's name in user memory.

## Language migration

Legacy `pt`, `pt-br`, and `pt_BR` values normalize to `pt-BR`. On the standard
local Piper path, the backend prepares the matching language voice in the
background and commits only when ready. Keep Settings open to see preparation
status. Failure leaves the prior STT/TTS configuration active.

Custom/cloned profiles are intentionally not replaced on language changes. If
a custom voice does not speak the target language well, select or create a
profile backed by a multilingual provider.

## Companion and voice state

Re-apply a companion once after upgrade if it predates the full-profile schema.
Future activation and startup prefer a voice bundled with that companion and
synchronize the dashboard selector. Downloads contain the saved companion
components selected for export, including a voice reference only when explicitly
requested and consented.

## VRM transforms and animations

Saved transforms take precedence. New/legacy private Torikinoko or MINIUS packs
without a stored transform receive a 180° Y default. Use the Settings transform
controls to override it. Discover clips, inspect the returned names, map each
lifecycle selector, then save/apply the avatar settings.

If discovery reports no clips, the VRM has no embedded animation tracks for
OpenMimicry to map. Import another model or add animations in an external DCC
pipeline before reimporting.

## Tools and Claude

Tools remain opt-in and policy-gated. The built-in alarm writes a durable local
alarm/notification; it does not control the platform Clock application. Check
the backend log for `tool route`, `alarm scheduled`, `policy denied`, or
`fallthrough` entries.

Claude tasks require a working authenticated Claude Code CLI. The phrase
`ask claude` may occur anywhere after wake-name acceptance. An untouched working
directory of `.` resolves to the current Git/OpenMimicry root on first use;
explicit configured directories are never silently replaced.

## Rollback

1. Stop all processes.
2. Restore the previous source tree.
3. Restore the `~/.openmimicry` backup only if the older build cannot read a
   setting written by v1.9.1.

Removing v1.9.1 source does not delete imported companions, voices, memories, or
task history.
