# OpenMimicry v1.8.5 — Claude task runtime hotfix

OpenMimicry v1.8.5 fixes the silent Claude Code task failure observed on
Windows after a delegation was correctly classified and routed.

## Root causes addressed

The previous adapter discarded Claude's stderr when the process returned a
non-zero code, replacing the useful authentication, workspace-trust,
permission, path, or provider message with `exit 1`. A fast process could also
reach its terminal state before the dashboard subscribed to the journaled
update stream.

Windows adds two launcher concerns: a backend process can retain an older
`PATH` after Claude is installed, and npm installations expose `claude.cmd`,
which cannot be treated exactly like a native executable.

## Behavior in v1.8.5

- Discover `claude` from `PATH`, the official native
  `%USERPROFILE%\.local\bin\claude.exe` location, WinGet links, or the legacy
  npm launcher.
- Wrap `.cmd`/`.bat` launchers through `COMSPEC` without enabling a general
  shell task surface.
- Preserve Windows process variables required by Claude while continuing to
  exclude unrelated environment secrets.
- Use explicit `--input-format text`, stream JSON, verbose output, and a
  configurable permission mode.
- Retain and display the actual terminal error everywhere: diagnostic log,
  live card, SQLite history, result, and notification.
- Replay already-observed updates to late subscribers.
- Add **Tasks → Runtime readiness**, which runs `claude --version` and
  `claude auth status` without making a model request.

## Existing configuration

The v1.8.4 `config/user.yaml` remains valid. The optional setting below makes
the default explicit:

```yaml
tasks:
  runtimes:
    claude_code:
      permission_mode: acceptEdits
```

Before the first non-interactive task in a repository, run `claude` once from
that exact directory and accept its workspace-trust prompt.

