# Task delegation

OpenMimicry's job is not to be the agent. Its job is to be a comfortable, embodied interface to *whatever* the user wants to delegate work to. The task delegation module exposes a single contract — `TaskRuntimeAdapter` — and ships several reference implementations. Users can write their own without forking the project.

## 1. Contract

```python
# packages/openmimicry-tasks/src/openmimicry/tasks/base.py
class TaskRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]

    async def submit(self, req: TaskRequest) -> TaskHandle: ...
    async def status(self, handle: TaskHandle) -> TaskStatus: ...
    async def cancel(self, handle: TaskHandle) -> None: ...
    def updates(self, handle: TaskHandle) -> AsyncIterator[TaskUpdate]: ...
    async def result(self, handle: TaskHandle) -> TaskResult: ...
    async def healthcheck(self) -> bool: ...
```

Schemas:

```python
class TaskRequest(BaseModel):
    summary: str                          # short human description
    instructions: str                     # full task text
    inputs: list[TaskInput] = []          # files, URLs, blobs
    capabilities_required: set[str] = set()
    preferred_runtime: str | None = None
    constraints: TaskConstraints = TaskConstraints()
    metadata: dict[str, Any] = {}

class TaskUpdate(BaseModel):
    handle: TaskHandle
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    note: str | None = None
    progress: float | None = None
    stdout: str | None = None
    artifacts: list[Artifact] = []
    error: TaskError | None = None
    ts: datetime
```

The `updates(...)` stream is the live channel: status changes, log lines, progress, intermediate artifacts. The avatar/runtime only consumes this stream; it does not poll `status`.

## 2. Router

```python
class TaskRouter(TaskRuntimeAdapter):
    """A TaskRuntimeAdapter whose impl is 'pick the right adapter'."""
    def __init__(self, registry: dict[str, TaskRuntimeAdapter], cfg: TasksConfig): ...
```

Selection order:

1. `req.preferred_runtime` if set and healthy.
2. The first adapter whose `capabilities` is a superset of `req.capabilities_required`.
3. `cfg.default_runtime` if healthy.
4. Otherwise fail with `NoAdapterForCapabilities`.

The router is itself a `TaskRuntimeAdapter`, so the runtime only ever knows one type.

## 3. Reference adapters

| Adapter | Capabilities | Underlying |
|---|---|---|
| `mcp_agent_adapter` | `{"mcp", "tools", "browse"}` | [`mcp-agent`](https://github.com/lastmile-ai/mcp-agent) |
| `claude_code_adapter` | `{"shell", "code_edit", "repo"}` | `claude` CLI |
| `openclaw_adapter` | declared per build | OpenClaw runtime |
| `picoclaw_adapter` | declared per build | PicoClaw runtime |
| `local_shell_adapter` | `{"shell"}` | subprocess + allowlist |
| `mock_adapter` | `{"mock"}` | in-memory, for tests |

Each adapter has its own subpackage under `packages/openmimicry-tasks/src/openmimicry/tasks/adapters/`, with a single `.py` file per runtime so dependencies stay isolated.

### 3.1 mcp-agent adapter

`mcp-agent` is an excellent fit because it already handles MCP connections, LLM workflows, external signals, and persistent state. The OpenMimicry adapter:

- Reads `tasks.runtimes.mcp_agent.servers` from config and starts those MCP servers.
- Translates `TaskRequest.instructions` into an mcp-agent run.
- Subscribes to mcp-agent's event stream and republishes those as `TaskUpdate`s.

It is *optional*: if the user does not declare an `mcp_agent` runtime, the package does not import `mcp-agent` at all.

### 3.2 Claude Code adapter

Spawns `claude` (the Claude Code CLI) in a child process with a constrained working directory and streams its output. The adapter:

- Locates `claude` from config or PATH.
- Builds the prompt from `TaskRequest.instructions` plus the contents of any `TaskInput` files.
- Streams stdout/stderr; parses recognisable events ("Wrote file ...", "Ran command ...") into structured `TaskUpdate.note` lines.
- Cancels by sending SIGTERM, then SIGKILL after a grace window.

### 3.3 OpenClaw / PicoClaw adapters

These talk to local runtime processes over their respective transports. They are gated behind extras (`pip install openmimicry[openclaw]`).

### 3.4 Local shell adapter

The dangerous one, so it is the most constrained:

- Hard allowlist of commands and flags loaded from config.
- Single fixed working directory per `TaskRequest`.
- No shell metacharacter interpolation — `shlex.split` and `subprocess.run(..., shell=False)`.
- Read/write scope (which paths the command may touch) is recorded in `TaskUpdate.metadata` for audit.

The adapter exists to make "Mimi, list files in this folder" trivial without giving up safety. It is *not* a general-purpose code execution surface; users who want that should use Claude Code or an MCP-based runtime.

### 3.5 Mock adapter

Returns scripted updates deterministically. Used by `tests/integration/test_tasks.py` to assert routing, cancellation, and update fanout.

## 4. Wiring with the LLM

The LLM can call into tasks two ways:

- **Explicit user request.** "Ask Claude to refactor this file." The runtime detects this with a tiny intent classifier (regex first, LLM second) and emits a `TaskRequest`.
- **Tool calls.** Adapters can be exposed as LLM tools via `ToolSpec`. The LLM picks the tool, the runtime fills out a `TaskRequest`, and the router dispatches.

The frontend renders a **task card** (separate from the speech bubble) for every active task, showing summary, status, progress, and a cancel button. Updates flow in via the WebSocket projection as `TaskCardEvent`.

## 5. Safety and observability

- All `TaskRequest`s are logged with summary, inputs, and chosen adapter.
- `TaskUpdate.stdout` is rate-limited so an adapter that streams MBs of logs cannot blow up memory.
- The user can revoke an adapter at runtime through the panel UI; the router refuses to route to it until re-enabled.
- The local shell adapter writes an explicit audit line to disk for every command, with timestamps and exit code.

## 6. Testing

- Unit tests per adapter: `tests/unit/tasks/test_<adapter>.py` with the underlying process or library mocked.
- Routing tests: `tests/integration/test_task_routing.py` with mock adapters of varied capabilities.
- Cancellation: `tests/integration/test_task_cancel.py` confirms `cancel()` reliably terminates the underlying process and produces a `TaskUpdate(status="cancelled")`.
