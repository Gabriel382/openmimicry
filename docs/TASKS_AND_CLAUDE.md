# Tasks and local Claude Code

This guide describes the behavior implemented in OpenMimicry v1.8.5. It
distinguishes conversational replies from delegated tasks and shows how to use
an existing Claude subscription through the locally installed `claude` CLI.
An Anthropic API key is optional.

## What a task is

A normal prompt is sent to the selected conversation LLM. A task is created
only for an explicit delegation phrase:

- `Ask Claude to add tests for the parser`
- `Tell Claude Code to review the current project`
- `Run the local shell to ...`
- `Ask the MCP agent to ...`

The regex-first intent detector selects a named runtime, the task router starts
that adapter, and the journal records its request, updates, result, artifacts,
and terminal notification in SQLite. The default database is:

```text
~/.openmimicry/tasks/tasks.sqlite3
```

The avatar toolbar's bell opens the notification/history section. Notifications
are deliberately separate from the conversation, so task completion does not
overwrite an unrelated assistant reply.

Current scheduling boundary: the adapter process runs asynchronously, but the
accepted task owns the single conversation turn lease until it reaches a
terminal state. A second chat submission is rejected during that lease instead
of being hidden in a queue. Restart-safe history survives, but an interrupted
external process is not silently resumed after OpenMimicry exits.

## Connect a Claude subscription (no API key)

Claude Code must already be installed and authenticated for the same Windows
account that launches OpenMimicry.

```powershell
claude --version
claude
```

On first launch, complete the browser login with the Claude Team account. From
an interactive Claude prompt, `/login` changes or repairs the account. These
are the authentication paths documented by Anthropic:

- <https://docs.anthropic.com/en/docs/claude-code/quickstart>
- <https://docs.anthropic.com/en/docs/claude-code/iam>

Add the task runtime to `config/user.yaml`. This overlay works even when the
backend is launched with `start-openrouter-voice.ps1`:

```yaml
tasks:
  default_runtime: claude_code
  database_path: ~/.openmimicry/tasks/tasks.sqlite3
  runtimes:
    claude_code:
      adapter: claude_code
      cli: claude
      auth_mode: subscription
      permission_mode: acceptEdits
      working_dir: C:/Users/henri/Documents/git/personal
```

Restart the backend once after registering a new task adapter. Existing avatar,
voice, memory, and 3D-transform dashboard changes do not require this task
registration restart.

Before delegating to a repository for the first time, open Claude interactively
from that exact repository and accept its workspace-trust prompt:

```powershell
cd C:\Users\henri\Documents\git\personal\openmimicry
claude
```

Then exit the interactive session. OpenMimicry's **Tasks → Runtime readiness**
control runs `claude --version` and `claude auth status` with the same curated
environment and working directory as a real task. These checks do not submit a
model request or consume Claude usage.

In `subscription` mode OpenMimicry intentionally omits
`ANTHROPIC_API_KEY` from the child environment. The adapter runs:

```text
claude -p --output-format stream-json --verbose
```

and sends task instructions on standard input. This follows Claude Code's
documented print/structured-output interface:
<https://docs.anthropic.com/en/docs/claude-code/cli-reference>.

To use API billing instead, set `auth_mode: api` and provide
`ANTHROPIC_API_KEY` in the launching process. Do not place the token in YAML.

## Choosing the project folder

The `working_dir` above is the default for conversational delegation. For a
single fixed repository, point it directly at that repository.

For several repositories, create named projects through the local task API:

```powershell
$project = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks/projects `
  -ContentType application/json `
  -Body (@{
    name = "OpenMimicry"
    root_path = "C:/Users/henri/Documents/git/personal/openmimicry"
    description = "Desktop companion"
    provider_runtime = "claude_code"
  } | ConvertTo-Json)
```

Submit work against the returned project id:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType application/json `
  -Body (@{
    summary = "Review avatar persistence"
    instructions = "Inspect the implementation, run tests, and report findings."
    project_id = $project.project.id
    preferred_runtime = "claude_code"
    capabilities = @("code")
  } | ConvertTo-Json)
```

Project roots are resolved server-side and become the child process working
directory. A conversational `Ask Claude to ...` phrase uses the runtime's
default `working_dir`; it does not guess a project from casual conversation.

## Diagnose Claude task availability

1. Run `claude --version` in the same PowerShell window/account.
2. Run `claude`, confirm the correct Team account, then exit.
3. Confirm `tasks.runtimes.claude_code` exists in `config/user.yaml`.
4. Run `claude` once inside the configured `working_dir` and accept workspace
   trust.
5. Restart the backend and open **Tasks → Runtime readiness**.
6. Submit `Ask Claude to list the project files without changing them`.
7. Watch the Tasks card, then the toolbar bell.

Typical failures are explicit:

- `claude CLI not found`: use an absolute `cli:` path or repair `PATH`.
- `spawn_failed`: the configured `working_dir` does not exist or is denied.
- authentication output from Claude: run `claude` interactively and `/login`.
- preferred runtime not registered: add it under `tasks.runtimes` and restart.
