---
name: "M5: openmimicry-tasks"
about: TaskRouter, mcp-agent, Claude Code, local-shell adapters
title: "[M5] openmimicry-tasks — TaskRouter + mcp-agent / Claude Code / local-shell"
labels: ["module", "M5", "tasks"]
assignees: []
---

## Overview

Task delegation: router + concrete adapters for mcp-agent, Claude Code, and an allowlisted local shell.

**Parallelism: parallel with M1, M2, M3, M7.** Depends on Phase 0 and M0.

## Required reading

1. [`docs/contracts.md`](../docs/contracts.md) §6
2. [`docs/modules/M5_tasks.md`](../docs/modules/M5_tasks.md)
3. [`docs/task_delegation.md`](../docs/task_delegation.md)
4. [mcp-agent docs](https://github.com/lastmile-ai/mcp-agent)

## LLM brief

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

## Definition of done

See [`docs/modules/M5_tasks.md`](../docs/modules/M5_tasks.md).
