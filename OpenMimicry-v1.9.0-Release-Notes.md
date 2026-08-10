# OpenMimicry v1.9.0 — Persistent companions, multilingual interaction, and background agents

OpenMimicry v1.9.0 makes a configured companion a durable unit rather than a
loose collection of settings. It also turns Claude Code delegation into a
project-aware background workflow and introduces a conservative,
provider-neutral tools layer.

## Highlights

### One saved companion, restored atomically

- The last activated companion is rehydrated before voice and avatar adapters
  are constructed. The checked-in Octomimic remains the first-run fallback.
- Companion profile schema v2 includes the character pack and compatible
  runtime, Three.js scale/position/rotation/framing, animation speed and clip
  aliases, voice profile, personality prompt, assistant name, and recognition
  aliases.
- Activating a profile warms its voice before committing the selection. A
  failed candidate leaves the current companion usable.
- Manual pack or voice selection intentionally clears the saved profile
  selector, so an old profile cannot silently undo the user's latest choice.

### Correct assistant identity and cleaner speech

- Deterministic memory stores a user's name as `user_name`, not the ambiguous
  key `name`. Legacy `name` records are normalized when used as context.
- Memory facts are explicitly described as facts about the user and cannot
  override the assistant identity defined by personality settings.
- Assistant name and aliases are saved with the personality and full companion
  profile.
- URLs, Markdown links, and citation markers remain visible in text but are
  removed from the TTS copy. The companion no longer reads long links aloud.

### Reliable research and multilingual input/output

- OpenRouter's default research mode is `auto`: explicit questions about the
  internet, current facts, weather, time, or sources trigger research;
  greetings and ordinary conversation do not.
- When research is enabled, the system contract prevents the model from
  claiming that no internet access exists. Sources are shown only when the
  user asks for them.
- Input and output language can be selected independently from English,
  French, Spanish, Portuguese, or automatic detection. A multilingual STT
  model is warmed before the change is committed.

### Claude Code projects run beside the conversation

- Direct forms such as `Claude, ...`, `Ask Claude to ...`, and `Launch Claude
  to ...` are classified deterministically.
- Claude CLI path, subscription/API authentication mode, project directory,
  permission mode, model, and maximum turns are editable in the dashboard.
- Projects are registered once. A cheap Git fingerprint controls Claude
  session reuse: unchanged repositories may resume; changed repositories begin
  with fresh context instead of trusting stale state.
- Delegation returns immediately with a confirmation while the task continues
  in the background. Durable progress, terminal results, and notifications are
  kept in SQLite. The desktop notification button lights when work finishes.

### Optional local tools

- A new provider-neutral policy supports a small deterministic vocabulary:
  browser links, Spotify search, new text files, folders, configured
  applications, and alarms.
- Tools are off by default. File and folder access is limited to configured
  roots; applications are exact aliases; text files are create-only; arbitrary
  shell commands are never inferred.
- An endpoint provider accepts `{\"text\": ...}` and returns
  `{\"handled\": true, \"spoken_reply\": \"...\"}`, allowing another desktop
  service or an Android implementation to replace the built-in executor.

### Private 3D imports and animation mapping

- Three.js settings now persist X/Y/Z rotation and per-lifecycle animation
  aliases for imported VRM clips.
- The dashboard accepts the original Torikinoko and MINIUS creator ZIPs using
  credit presets. The importer copies only the sole VRM to the private data
  directory and writes a local manifest.
- Torikinoko and MINIUS model bytes are not redistributed by OpenMimicry. Their
  original terms prohibit redistribution; users must obtain and import the
  original archives themselves.

## Compatibility and safety

- Configuration schema remains version 2; all v1.8 user overlays remain valid.
- Companion v1 imports remain accepted and are upgraded to v2 when exported.
- Memory and voice stay optional. Tools are disabled by default.
- Local characters, voice references, personalities, companion exports,
  credentials, logs, memory databases, and task journals remain ignored by
  source control.
- OpenMimicry source remains MIT. Imported models, optional providers, cloud
  services, voice models, and user assets retain their own terms.

See [MIGRATION-v1.9.0.md](MIGRATION-v1.9.0.md) and
[docs/V1.9.0_USER_GUIDE.md](docs/V1.9.0_USER_GUIDE.md).
