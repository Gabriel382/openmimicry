# Migrating to OpenMimicry v1.8.3

Version 1.8.3 is a backward-compatible asset release. Configuration schema 2
does not change.

1. Commit or back up local work.
2. Merge or replace the source with v1.8.3.
3. Re-run the installation profile already used for v1.8.2.
4. Start the backend and desktop normally.
5. In Settings, select runtime `threejs` and character pack
   `octomimic_vrm`, then apply the selection.

The built-in model now exists at
`characters/octomimic_vrm/octomimic.vrm`. Do not replace it to test the
shipped fixture. Put custom VRM files in the private character directory or
import them through the dashboard so Git continues to exclude local and
potentially copyrighted assets.

Existing private characters, companion profiles, personalities, voice
references, memory data, task journals, credentials, and downloaded models
remain outside the release archive.
