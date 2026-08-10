# OpenMimicry v1.9.0 verification record

Verification was performed against the packaged v1.9.0 source tree on
2026-08-02. Network-backed model calls and physical audio playback were not
required by the automated suite.

## Automated results

| Check | Result |
|---|---|
| Python collection | 659 tests collected |
| Python test suite | Pass, 659/659 |
| Ruff formatting | Pass |
| Ruff lint | Pass |
| Frontend Vitest | Pass, 20 files and 100 tests |
| TypeScript check | Pass |
| Vite production build | Pass; non-blocking large-chunk advisory only |
| Dashboard JavaScript syntax | Pass (`node --check`) |
| Version consistency | Pass, 27 version declarations at 1.9.0 |
| Bundled Octomimic VRM generation/loader tests | Pass |

Rust/Tauri compilation was not rerun in this Linux packaging environment
because `cargo` is unavailable. No Rust behavior changed in v1.9; Rust edits
are version metadata only. The frontend and production bundle consumed by
Tauri were both verified.

## New regression coverage

- saved companion rehydrates its VRM/runtime and voice before adapter wiring;
- full companion v2 identity, transform, animation aliases, and voice path;
- legacy memory identity cannot rename the assistant;
- direct Claude intent phrases and configurable Claude model arguments;
- Git fingerprint/session-resume guard for registered projects;
- background task acknowledgement and durable notification behavior;
- deterministic file tool creates a new file without speaking its contents;
- Three.js lifecycle and gesture clip aliases;
- original creator VRM ZIP import copies only the model and writes credits;
- dashboard exposes language, tools, Claude projects/settings, private VRM
  import, and 3D alias controls.

## Creator-archive acceptance

Both user-supplied original archives were tested through the production
private importer:

| Preset | Result |
|---|---|
| Torikinoko | Imported one valid VRM (2,605,408 bytes); auxiliary files excluded |
| MINIUS | Imported one valid VRM (7,544,336 bytes); auxiliary files excluded |

The tests operated on local originals. Neither archive nor extracted model is
included in the release artifacts.

## Security and privacy checks

- archive traversal, symlinks, entry count, compressed size, expanded size,
  and glTF magic are checked before an import is committed;
- tools remain disabled by default and never execute arbitrary shell strings;
- local files/folders are confined to explicit roots, application launch uses
  exact aliases, and text creation never overwrites an existing file;
- voice references and companion/profile state remain outside the repository;
- source ZIP inspection confirms no uploaded Torikinoko/MINIUS bytes, secrets,
  environments, dependencies, caches, logs, local databases, or build output.
