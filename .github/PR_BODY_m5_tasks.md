# feat(tasks): M5 — TaskRouter + real adapters

Implements `docs/modules/M5_tasks.md` against the frozen contracts in
`docs/contracts.md`. Constraint respected: no imports from
`openmimicry-llm`, `openmimicry-voice`, or `openmimicry-avatar`.

## What lands

### Core surface

- `TaskRouter` — capability-based dispatcher; itself a `TaskRuntimeAdapter`.
  Selection order: **preferred runtime → capability superset → default →
  `NoAdapterForCapabilities`**. Tracks `handle.id → adapter` so `status`,
  `cancel`, `updates`, and `result` route back to the originating
  adapter.
- `MockTaskRuntimeAdapter` — scripted mock that replaces the Phase 0
  stub. Accepts `scripted_updates`, auto-appends a terminal
  `succeeded` if none was scripted, and supports
  `cancel_flips_terminal=True` for cancel-path tests.
- `detect_task_intent(text)` — regex-first classifier returning
  `TaskRequest(preferred_runtime, capabilities_required)` for:
  - `ask claude to …` → `claude_code` + `{code, files}`
  - `send this to claude: …` → `claude_code` + `{code, files}`
  - `use the mcp agent to …` → `mcp_agent` + `{mcp}`
  - `run shell to …` → `local_shell` + `{shell}`
- `errors.py`: `TaskRoutingError`, `NoAdapterForCapabilities`,
  `TaskAdapterError`; re-exports `TaskError`.

### Concrete adapters

- **`LocalShellAdapter`** — the dangerous one, locked down:
  - **Allowlist-or-reject.** Each `AllowlistEntry` declares
    `cmd`, `flag_patterns: tuple[re.Pattern, ...]`, optional
    `positional_pattern`, and `max_args`. Substring matching is not
    used anywhere.
  - **No shell.** `shlex.split` on the instruction, then
    `asyncio.create_subprocess_exec(*argv, shell=False)`. `argv[0]`
    must be a bare command name (no path components).
  - **Path safety.** `working_dir` is resolved against the project
    root with `Path.resolve(strict=True)`; traversal attempts are
    rejected before exec.
  - **Cancel.** SIGTERM, wait `cancel_grace_s`, SIGKILL.
  - **Audit log.** Every accepted *and* rejected argv is written to
    `audit_log` (JSONL) with timestamp + rejection reason.
- **`ClaudeCodeAdapter`** — wraps the `claude` CLI:
  - Resolves the binary via `shutil.which` or an absolute path; the
    path is never inherited from the caller's `PATH` blindly.
  - **Curated env.** Only `PATH`, `HOME`, `ANTHROPIC_API_KEY`,
    `ANTHROPIC_BASE_URL`, `CLAUDE_HOME` are forwarded, plus any
    caller-declared overrides. A planted `UNRELATED_SECRET` in the
    parent env is asserted to *not* leak in the test suite.
  - Parses `Wrote file:`, `Ran command:`, `Error:` lines into
    `TaskUpdate.note` and `Artifact` records.
- **`MCPAgentAdapter`** — lazy-imports `mcp_agent` inside `submit` /
  `healthcheck`. If the extra isn't installed, raises
  `MCPAgentUnavailable("mcp-agent is not installed. Install with
  pip install \"openmimicry-tasks[mcp-agent]\"")`. Tolerates the
  `Agent.run()` shape variations across mcp-agent versions
  (async-iterator *or* coroutine returning a final result).
- **`OpenClawAdapter` / `PicoClawAdapter`** — stubs that raise
  `NotImplementedError` pointing at
  `docs/modules/post_v0_2_modalities.md`. They satisfy the Protocol
  shape so accidental wiring is loud rather than silent.

### Entry-point registration

`packages/openmimicry-tasks/pyproject.toml` declares four
`openmimicry.contracts.task_runtime` entry points: `mock`,
`local_shell`, `claude_code`, `mcp_agent`. Each module exposes a
`make_*_adapter()` factory.

### Tests

- `tests/unit/tasks/test_mocks.py` — Protocol satisfaction, scripted
  updates, terminal append, cancel-flip, unknown handle.
- `tests/unit/tasks/test_intent.py` — pattern coverage + null cases.
- `tests/unit/tasks/test_router.py` — preferred, capability superset,
  default fallback, no-match, unknown preferred falls through,
  cross-adapter cancel dispatch.
- `tests/unit/tasks/test_local_shell_adapter.py` — rejects unknown
  command / unknown flag / path-component cmd / relative cmd /
  path-traversal `working_dir`; audit log is written on rejection;
  successful echo + cancel terminates the process (POSIX-only via
  `pytest.mark.skipif`).
- `tests/unit/tasks/test_claude_code_adapter.py` — `_FakeProcess` +
  fake stream readers prove: unavailable when CLI missing, success
  streams stdout, nonzero exit → `failed`, env is curated
  (`UNRELATED_SECRET` does not leak), `extra_args` are forwarded.
- `tests/unit/tasks/test_mcp_agent_adapter.py` — injects a fake
  `mcp_agent` module via `sys.modules`: unavailable when missing,
  run streams events, cancel marks `cancelled`, exception in the
  event stream → `failed`.
- `tests/contract/test_task_runtime.py` — un-skipped under a
  hermetic guard (`mock` always; `local_shell` admitted when
  `RUN_LOCAL_SHELL_CONTRACT=1`).

## Safety posture

`LocalShellAdapter` enforces allowlist-or-reject with `shell=False`
and a full audit trail. `ClaudeCodeAdapter` does not pass the
parent's environment beyond a curated whitelist. `MCPAgentAdapter`
fails closed when the optional extra is absent.

## Out of scope (deferred)

- M6 (FastAPI + WS bridge → frontend) — M5 ships the substrate; the
  HTTP/WS surface lands in its own brief.
- `OpenClawAdapter` / `PicoClawAdapter` concrete implementations
  (post-v0.2).

Closes the M5 task.
