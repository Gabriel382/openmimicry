# Migrating from OpenMimicry v1.8.5 to v1.9.0

No destructive configuration or database migration is required. Schema v2,
the existing voice-profile store, memory database, and task journal remain
compatible.

## Upgrade

1. Stop the backend and desktop shell.
2. Back up `.env`, `config/user.yaml`, and `~/.openmimicry`.
3. Replace the v1.8.5 source with v1.9.0, preserving those private files.
4. Run the ordinary install/update command for your profile.
5. Start the backend once. The saved companion selector is read before avatar
   and voice adapters are built.
6. Open `http://127.0.0.1:8000/dashboard` and verify the active companion,
   voice, personality name/aliases, languages, web mode, Claude settings, and
   tool policy.

Windows integrated profile:

```powershell
.\scripts\win\install.bat integrated
$env:OPENMIMICRY_PROFILE = "integrated"
.\scripts\win\backend.bat --no-reload
```

## Identity and legacy memory

New deterministic facts use `user_name`. Existing local facts with key `name`
are interpreted as the user's name when injected into a prompt; the database
does not need to be rewritten. Review or delete an incorrect record from the
Memory panel if it was meant to describe the assistant.

Set the assistant's actual identity under **Personality → Assistant name and
aliases**. Saving a full companion profile now includes those fields.

## Companion profiles

Existing v1 companion ZIPs still import. Activate the profile, confirm its
voice and avatar, then export it again to create a v2 profile containing:

- assistant name and aliases;
- personality prompt;
- avatar pack, runtime, position, scale, rotation, framing, speed, and clip
  aliases;
- selected voice profile and optional consented voice reference.

Private profiles and references remain under `~/.openmimicry` and are not
tracked by Git.

## Language

English remains the default. Choosing `auto`, French, Spanish, or Portuguese
for input may replace an English-only Whisper model with
`distil-large-v3`. The backend enters a visible refreshing state, warms the
candidate, and rolls back if preparation fails.

## Claude Code

The v1.8.5 Claude settings remain valid. v1.9 adds optional `model` and
`max_turns` values and registered projects.

1. Run `claude` interactively once in each repository and accept workspace
   trust.
2. In the dashboard, save the Claude CLI settings.
3. Register each project by name and absolute root directory.
4. Submit a dashboard task or say `Ask Claude to ... in <project name>`.

Tasks run asynchronously. Closing the dashboard does not delete their SQLite
history. A repository fingerprint prevents resuming stale Claude context after
the Git checkout changes.

## Tools

Tools are intentionally disabled during migration. Review allowed roots and
individual capabilities before switching them on. Application aliases must map
to an exact executable path/name; arbitrary model-generated commands are not
run.

## Creator VRMs

Torikinoko and MINIUS are not bundled because their original terms do not
permit redistribution. Obtain the creator's original ZIP, choose the matching
preset under **Avatar settings → Import original VRM creator ZIP**, and import
it locally. The archive itself is never added to the repository or release.

## Rollback

Stop v1.9, restore the v1.8.5 source and the backup of `config/user.yaml`, then
restart. Task-journal columns added by v1.9 are additive and ignored by v1.8.5.
Keep a backup if you require a byte-for-byte rollback.
