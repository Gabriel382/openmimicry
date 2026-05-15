# Module M5: `openmimicry-tasks`

## Goal (1 line)

Ship `TaskRouter`, `mcp_agent_adapter`, `claude_code_adapter`, `local_shell_adapter`, and `MockTaskRuntimeAdapter` so the backend can submit `TaskRequest`s, stream `TaskUpdate`s back to the avatar, and cancel cleanly.

## Scope and non-scope

**In scope.**

- `TaskRouter` — capability-based routing across registered adapters; itself a `TaskRuntimeAdapter`.
- `mcp_agent_adapter` — bridges to the `mcp-agent` library.
- `claude_code_adapter` — spawns and supervises the `claude` CLI.
- `local_shell_adapter` — allowlisted subprocess execution.
- `MockTaskRuntimeAdapter` — canonical fixture other modules consume.
- A small intent classifier (regex-first, LLM-fallback later) under `openmimicry.tasks.intent` that detects "ask Claude to ...", "send this to ..." patterns.
- Per-adapter audit logs where applicable (especially `local_shell`).

**Non-scope.**

- The `TaskRuntimeAdapter` Protocol (Phase 0).
- The LLM tool-call binding (M1 owns the Protocol; M6 wires it into the chat path).
- The frontend task-card UI (M7).
- OpenClaw, PicoClaw adapters — these are stub-only in M5; concrete implementations are post-v0.2.0 with their own briefs.

## Inputs (immutable, from contracts.md)

- `TaskRuntimeAdapter` Protocol (`contracts.md` §6).
- Schemas: `TaskRequest`, `TaskHandle`, `TaskUpdate`, `TaskResult`, `TaskStatus`, `TaskInput`, `TaskConstraints`, `TaskError`, `Artifact` (`contracts.md` §6).
- `TasksConfig` from `AppConfig.tasks` ([`../configuration.md`](../configuration.md)).
- `TaskSubmitted`, `TaskUpdatedEvent`, `TaskCompleted` events (`contracts.md` §2.1) — published by M5 onto the bus.

## Outputs (this module owns)

```text
packages/openmimicry-tasks/
  pyproject.toml
  README.md
  src/openmimicry/tasks/
    __init__.py
    base.py                       # re-export of TaskRuntimeAdapter
    errors.py                     # TaskRoutingError, TaskAdapterError
    router.py                     # TaskRouter
    intent.py                     # detect_task_intent(text) -> TaskRequest | None
    adapters/
      __init__.py
      mcp_agent_adapter.py
      claude_code_adapter.py
      local_shell_adapter.py
      openclaw_adapter.py         # stub raising NotImplementedError("post-v0.2")
      picoclaw_adapter.py         # stub
    mocks.py                      # MockTaskRuntimeAdapter
tests/unit/tasks/
  test_router.py
  test_intent.py
  test_local_shell_adapter.py
  test_claude_code_adapter.py     # subprocess mocked
  test_mcp_agent_adapter.py       # mcp_agent mocked
tests/contract/test_task_runtime.py  # un-skipped
```

Optional deps:
- `[mcp-agent]`: `mcp-agent>=0.1`
- `[claude-code]`: nothing — uses the `claude` CLI on PATH
- `[tasks]`: aggregate of the above

## Mock implementations this module provides

```python
# openmimicry.tasks.mocks
class MockTaskRuntimeAdapter:
    name: str = "mock"
    capabilities: set[str] = {"mock", "shell"}

    def __init__(self, *, scripted_updates: list[TaskUpdate] | None = None,
                 final_result: TaskResult | None = None) -> None: ...

    async def submit(self, req: TaskRequest) -> TaskHandle: ...
    async def status(self, handle: TaskHandle) -> TaskStatus: ...
    async def cancel(self, handle: TaskHandle) -> None: ...
    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]: ...
    async def result(self, handle: TaskHandle) -> TaskResult: ...
    async def healthcheck(self) -> bool: ...
```

The mock yields its scripted updates with a small async sleep between them, then completes. Other modules' tests drive end-to-end task flows against this.

## Test surface

- **Contract.** `tests/contract/test_task_runtime.py` parametrises over `MockTaskRuntimeAdapter`, `LocalShellAdapter`, `ClaudeCodeAdapter(mock)`, `MCPAgentAdapter(mock)`.
- **Unit.** `TaskRouter` selection order: preferred_runtime → capability superset → default → fail. Cancellation propagates to the chosen adapter.
- **Unit.** `LocalShellAdapter` rejects commands not on the allowlist; rejects flag values that don't match patterns; resolves `working_dir`; appends to the audit log; cancels via `process.kill()` with grace.
- **Unit.** `ClaudeCodeAdapter` spawns `claude` (mocked), pipes instructions, parses stdout into `TaskUpdate`s, cancels via SIGTERM→SIGKILL.
- **Unit.** `MCPAgentAdapter` constructs an mcp-agent run (mocked), forwards events.
- **Unit.** `detect_task_intent("Ask Claude to refactor utils.py")` returns a `TaskRequest(preferred_runtime="claude_code", ...)`.
- **Unit.** Streaming back-pressure: `updates(handle)` does not block on slow consumers (uses bounded queue + drop-with-warning per the same policy as `EventBus`).

## Step-by-step plan (atomic, numbered)

1. Create `packages/openmimicry-tasks/pyproject.toml` with optional deps.
2. Replace Phase 0 stub `mocks.py` with `MockTaskRuntimeAdapter`. Internally uses an `asyncio.Queue[TaskUpdate]` per handle.
3. Implement `errors.py`: `TaskError` (re-export from schemas), `TaskRoutingError`, `TaskAdapterError`, `NoAdapterForCapabilities`.
4. Implement `router.py::TaskRouter` per `docs/task_delegation.md` §2. Subscribes to no events; its own `submit` is the entry point. Holds `dict[str, TaskRuntimeAdapter]`. Selection algorithm: preferred → capability superset → default. `cancel(handle)` dispatches based on `handle.runtime`.
5. Implement `intent.py::detect_task_intent(text) -> TaskRequest | None`. Regex patterns for "ask <claude|claude code|mcp agent> to ...", "send this to ...", "use the local shell to ...". Return None if no match — the caller falls back to normal LLM chat.
6. Implement `adapters/local_shell_adapter.py`:
   - Loads allowlist from `LocalShellConfig`.
   - On `submit(req)`: build the argv from `req.instructions` (split with `shlex`), match against the allowlist (cmd + flag pattern), reject otherwise.
   - Run `asyncio.create_subprocess_exec(*argv, cwd=working_dir, stdout=PIPE, stderr=PIPE)`.
   - Stream stdout line-by-line into `TaskUpdate(stdout=line)`.
   - On completion, emit `TaskUpdate(status="succeeded")` and a `TaskResult`.
   - Append every command + exit code to `audit_log`.
   - `cancel`: `proc.terminate()` then `proc.kill()` after `cfg.cancel_grace_s`.
7. Implement `adapters/claude_code_adapter.py`. Locates `claude` from `cfg.cli` or PATH (`shutil.which`). Constructs the prompt from `req.instructions` + inputs file contents. Subprocess streaming the same way as local_shell. Parses recognisable lines: "Wrote file ...", "Ran command ...", "Error: ..." into `TaskUpdate.note`. Returns a `TaskResult` with `artifacts` for any new files Claude reports.
8. Implement `adapters/mcp_agent_adapter.py`. Lazy-import `mcp_agent`. On `submit(req)`: construct an `Agent` with the configured servers, kick off the run, subscribe to the run's event stream, translate each event to a `TaskUpdate`. Cancel via the run handle.
9. Stub `openclaw_adapter.py` and `picoclaw_adapter.py`: classes that satisfy the Protocol but `submit` raises `NotImplementedError("Post-v0.2 modality; see docs/modules/post_v0_2_modalities.md")`.
10. Register all four real adapters via entry point `openmimicry.contracts.task_runtime`.
11. Un-skip the contract test for the real adapters.
12. Write the unit tests. For `LocalShellAdapter`, use `tmp_path` for `working_dir` and audit log; assert path traversal attempts (`../../etc/passwd`) are rejected.
13. Write `packages/openmimicry-tasks/README.md`.
14. Update `CHANGELOG.md`.
15. `make ci`. Open PR `feat(tasks): M5 — TaskRouter + mcp-agent / Claude Code / local-shell adapters`.

## Definition of done (checklist)

- [ ] `from openmimicry.tasks import TaskRouter, MockTaskRuntimeAdapter, detect_task_intent` works.
- [ ] `TaskRouter` selection algorithm covered by unit tests for all four code paths.
- [ ] `LocalShellAdapter` rejects unsafe commands (`rm -rf /`, `; cat /etc/passwd`, allowlist bypass attempts).
- [ ] `ClaudeCodeAdapter` cancels within `cancel_grace_s` (default 3s) via SIGTERM → SIGKILL.
- [ ] `MCPAgentAdapter` lazy-imports `mcp-agent` and surfaces a clean error if the extra is not installed.
- [ ] Audit log lines appear in `~/.openmimicry/shell-audit.log` per `local_shell` command (or wherever `cfg.audit_log` points).
- [ ] Streaming back-pressure: a slow consumer does not stall the adapter (bounded queue, drop-with-warning).
- [ ] Coverage ≥ 80% on `openmimicry-tasks` source.
- [ ] `scripts/check_imports.py` clean.
- [ ] `CHANGELOG.md` entry.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M5 (`openmimicry-tasks`)** of OpenMimicry. The `TaskRuntimeAdapter` Protocol and the task schemas are frozen.
>
> Read in order:
>
> 1. `docs/contracts.md` §6 — `TaskRuntimeAdapter`, every task schema.
> 2. `docs/modules/M5_tasks.md` — this brief.
> 3. `docs/task_delegation.md` — router, adapter behaviour, safety posture for `local_shell`.
> 4. `mcp-agent` library docs: https://github.com/lastmile-ai/mcp-agent
>
> Implement the 15-step plan. Critical invariants:
>
> - `LocalShellAdapter` is the dangerous one. Allowlist-or-reject, never substring-match. `shlex.split` only, `subprocess.run(shell=False)` always. Every command goes in the audit log.
> - `ClaudeCodeAdapter` calls a real CLI. Spawn with a fixed cwd; never inherit the parent's full environment beyond what's necessary.
> - `MCPAgentAdapter` lazy-imports `mcp_agent`. If the extra isn't installed, raise a clean ImportError pointing at `pip install openmimicry[mcp-agent]`.
>
> Ship `MockTaskRuntimeAdapter` early — M6 depends on it. Register every real adapter via the `openmimicry.contracts.task_runtime` entry point.
>
> Constraint: do not import from `openmimicry-llm`, `openmimicry-voice`, `openmimicry-avatar`. Open the PR titled `feat(tasks): M5 — TaskRouter + mcp-agent / Claude Code / local-shell` with the Definition-of-done checklist ticked.
