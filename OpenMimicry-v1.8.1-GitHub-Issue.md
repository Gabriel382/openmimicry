# v1.8.1 — Accept legacy schema-v2 `web_search` configuration

## Problem

OpenMimicry v1.8.0 introduced
`llm.backends.<name>.web_search_mode: off|auto|always`. Existing development
configuration files can still contain the earlier Boolean
`web_search: true|false` while already declaring `schema_version: 2`.

Because both forms use schema version 2, the numbered v1→v2 migration does not
run. Strict Pydantic validation rejects `web_search` as an extra field and the
backend exits before startup.

## Expected behavior

- `web_search: true` starts as `web_search_mode: auto`.
- `web_search: false` starts as `web_search_mode: off`.
- The current `web_search_mode` wins when both keys exist.
- Conversion is in memory; user YAML is never rewritten.
- Other unknown fields remain forbidden.
- Invalid legacy values identify the exact option and current replacement.
- A config-only hotfix does not repeat an already-passed Chatterbox preflight.

## Acceptance criteria

- [x] Exact reported configuration reproduces before the fix.
- [x] Same configuration loads after the fix.
- [x] True, false, textual Boolean, precedence, invalid-value, and
      non-destructive cases are tested.
- [x] Full Python suite passes.
- [x] Ruff, Pyright, import boundaries, version consistency, and compileall
      pass.
- [x] Frontend tests, TypeScript, and production audit pass.
- [x] Voice preflight marker stays compatible with v1.8.0.
- [ ] Windows target smoke test confirms the original command reaches backend
      application startup.
