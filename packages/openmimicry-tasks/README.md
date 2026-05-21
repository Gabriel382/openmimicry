# openmimicry-tasks

Task delegation for OpenMimicry: `TaskRouter`, concrete adapters (mcp-agent, Claude Code, local-shell), the canonical mock, and a small intent detector.

## What's in the box

- **`MockTaskRuntimeAdapter`** — scripted, deterministic; replaces the Phase 0 stub. Used by M6 and every integration test that wants to exercise the task pipeline offline.
- **`TaskRouter`** — composes one or more adapters. Selection algorithm: preferred → capability superset → default → fail. Itself satisfies `TaskRuntimeAdapter`.
- **`LocalShellAdapter`** — **allowlist-or-reject** subprocess execution. `shlex.split` only, never `shell=True`. Every command lands in an audit log. SIGTERM → SIGKILL cancel with grace.
- **`ClaudeCodeAdapter`** — spawns the `claude` CLI; pipes the prompt; parses `Wrote file …` / `Ran command …` / `Error: …` lines into `TaskUpdate.note` and `Artifact`s.
- **`MCPAgentAdapter`** — wraps `mcp-agent` (lazy-imported). If the extra isn't installed, surfaces a clean `MCPAgentUnavailable` pointing at the install command.
- **`OpenClawAdapter`, `PicoClawAdapter`** — post-v0.2 stubs that raise `NotImplementedError`.
- **`detect_task_intent(text)`** — regex-first detection of "Ask Claude to …", "Use the MCP agent to …", "Run the local shell to …" patterns.

## Install

```bash
pip install openmimicry-tasks                       # mocks + router + shell + Claude CLI
pip install "openmimicry-tasks[mcp-agent]"          # + mcp-agent
pip install "openmimicry-tasks[tasks]"              # everything
```

## Usage

```python
import asyncio
from openmimicry.tasks import (
    AllowlistEntry, LocalShellAdapter, LocalShellSettings,
    MockTaskRuntimeAdapter, TaskRouter,
)
from openmimicry.core.schemas.tasks import TaskRequest

async def main():
    shell = LocalShellAdapter(
        settings=LocalShellSettings(
            working_dir="/tmp",
            audit_log="~/.openmimicry/shell-audit.log",
            allowlist=(
                AllowlistEntry(cmd="ls", flag_patterns=("-la", "-l", "-a")),
            ),
        ),
    )
    router = TaskRouter(
        adapters={"local_shell": shell, "mock": MockTaskRuntimeAdapter()},
        default_runtime="mock",
    )
    handle = await router.submit(TaskRequest(
        summary="list /tmp",
        instructions="ls -la",
        preferred_runtime="local_shell",
        capabilities_required={"shell"},
    ))
    async for update in router.updates(handle):
        print(update.status, update.stdout or update.note or "")
    final = await router.result(handle)
    print("final:", final.status)

asyncio.run(main())
```

## Safety posture (`docs/task_delegation.md`)

- `LocalShellAdapter` is the only adapter that runs user-controllable argv. The allowlist matches the exact command name (no path component allowed) AND every flag against a regex. Positional args have their own regex. `working_dir` is resolved and rejected if it escapes the configured root.
- `ClaudeCodeAdapter` spawns the `claude` CLI with a curated env (PATH + ANTHROPIC_* only, plus explicit `env_overrides`). Never inherits the parent's full environment.
- `MCPAgentAdapter` is lazy-imported; the heavy `mcp-agent` install is opt-in.

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §6 — frozen `TaskRuntimeAdapter` + task schemas.
- [`docs/modules/M5_tasks.md`](../../docs/modules/M5_tasks.md) — module brief.
- [`docs/task_delegation.md`](../../docs/task_delegation.md) — adapter behaviour + safety posture.
