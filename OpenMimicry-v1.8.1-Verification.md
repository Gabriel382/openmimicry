# OpenMimicry v1.8.1 verification record

Date: 2026-07-30

## Reported failure

The supplied Windows log failed before backend startup with:

```text
llm.backends.openrouter.web_search
Extra inputs are not permitted
```

The failing schema-v2 configuration was recreated verbatim. It now loads with
`web_search_mode == "auto"` and does not modify its source file.

## Automated gates

| Gate | Result |
| --- | --- |
| Exact `web_search: true` reproduction | PASS |
| Configuration-loader regression module | PASS — 22 tests |
| Complete Python suite | PASS — 637 tests |
| Ruff lint | PASS |
| Ruff formatting | PASS — 423 files |
| Pyright | PASS — 0 errors, 0 warnings |
| Import-boundary check | PASS |
| Version-consistency check | PASS — 27 entries at 1.8.1 |
| Python compileall | PASS |
| Frontend Vitest | PASS — 17 files, 94 tests |
| Frontend TypeScript | PASS |
| pnpm production audit | PASS — no known vulnerabilities |

## Target-machine boundary

The original Windows command must still be smoke-tested on the user's machine
because the build environment does not contain Windows, the microphone/speaker,
the RTX 4070 runtime, the authenticated provider token, or the user's
Chatterbox reference voice.

No voice dependency changed in this hotfix. The v1.8.0 Chatterbox preflight
marker remains valid, preventing an unnecessary model download or warmup.
