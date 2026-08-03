# Migrating to OpenMimicry v1.8.2

Version 1.8.2 is a backward-compatible bugfix release. Configuration schema 2
does not change.

1. Commit or back up local work.
2. Merge or replace the source with v1.8.2.
3. Re-run the same install profile used for v1.8.1.
4. Start the backend and desktop normally.

Existing private characters, companion profiles, personalities, voice
references, memory data, task journals, credentials, and downloaded models
remain outside the release archive and must not be copied into Git.

If a model legitimately needs longer than the current deadline, change that
backend's `request_timeout_s` in the active profile or user configuration. Do
not disable the deadline: it is the recovery boundary that prevents an
indefinite thinking state.
