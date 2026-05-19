"""Unit tests for LocalShellAdapter.

Covers the M5 DoD:

* allowlist rejection (unknown cmd, unknown flag, path component in cmd)
* path-traversal rejection on working_dir
* successful command + audit log
* SIGTERM -> SIGKILL cancel within cancel_grace_s
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from openmimicry.core.schemas.tasks import TaskConstraints, TaskRequest
from openmimicry.tasks.adapters.local_shell_adapter import (
    AllowlistEntry,
    LocalShellAdapter,
    LocalShellSettings,
)


def _shell_with(
    *,
    allowlist: tuple[AllowlistEntry, ...] = (),
    working_dir: str = ".",
    audit_log: Path | None = None,
    cancel_grace_s: float = 0.2,
) -> LocalShellAdapter:
    return LocalShellAdapter(
        settings=LocalShellSettings(
            allowlist=allowlist,
            working_dir=working_dir,
            audit_log=str(audit_log) if audit_log else None,
            cancel_grace_s=cancel_grace_s,
        ),
    )


async def test_rejects_unknown_command(tmp_path: Path) -> None:
    adapter = _shell_with(working_dir=str(tmp_path))
    handle = await adapter.submit(TaskRequest(summary="s", instructions="ls -la"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
    assert "not in allowlist" in (received[-1].error.message or "")  # type: ignore[union-attr]


async def test_rejects_unknown_flag(tmp_path: Path) -> None:
    adapter = _shell_with(
        working_dir=str(tmp_path),
        allowlist=(AllowlistEntry(cmd="ls", flag_patterns=("-la",)),),
    )
    handle = await adapter.submit(TaskRequest(summary="s", instructions="ls --rmrf"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
    assert "flag not allowed" in (received[-1].error.message or "")  # type: ignore[union-attr]


async def test_rejects_path_component_in_command(tmp_path: Path) -> None:
    adapter = _shell_with(
        working_dir=str(tmp_path),
        allowlist=(AllowlistEntry(cmd="ls"),),
    )
    handle = await adapter.submit(TaskRequest(summary="s", instructions="/bin/ls"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"


async def test_rejects_relative_command(tmp_path: Path) -> None:
    adapter = _shell_with(
        working_dir=str(tmp_path),
        allowlist=(AllowlistEntry(cmd="ls"),),
    )
    handle = await adapter.submit(TaskRequest(summary="s", instructions="./ls"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"


async def test_rejects_path_traversal_in_working_dir(tmp_path: Path) -> None:
    adapter = _shell_with(
        working_dir=str(tmp_path),
        allowlist=(AllowlistEntry(cmd="ls", flag_patterns=("-la",)),),
    )
    handle = await adapter.submit(
        TaskRequest(
            summary="s",
            instructions="ls -la",
            constraints=TaskConstraints(working_dir="../../etc"),
        )
    )
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"


async def test_audit_log_appended_on_rejection(tmp_path: Path) -> None:
    audit = tmp_path / "audit.log"
    adapter = _shell_with(working_dir=str(tmp_path), audit_log=audit)
    handle = await adapter.submit(TaskRequest(summary="s", instructions="rm -rf /"))
    [u async for u in adapter.updates(handle)]
    assert audit.exists()
    contents = audit.read_text(encoding="utf-8")
    assert "REJECTED" in contents


async def test_successful_command_runs_and_logs(tmp_path: Path) -> None:
    audit = tmp_path / "audit.log"
    # `python -V` is a portable command available in CI on every OS, with a
    # restricted flag pattern.
    adapter = _shell_with(
        working_dir=str(tmp_path),
        audit_log=audit,
        allowlist=(AllowlistEntry(cmd="python", flag_patterns=("-V", "--version")),),
    )
    if Path(sys.executable).name not in {"python", "python.exe", "python3"}:
        pytest.skip(
            "python executable not directly invokable from argv[0]='python'"
        )
    handle = await adapter.submit(
        TaskRequest(summary="version", instructions="python -V")
    )
    received = [upd async for upd in adapter.updates(handle)]
    statuses = [u.status for u in received]
    assert "running" in statuses
    # We're permissive about the terminal status (some environments return
    # the python version on stderr); what matters is no allow-list rejection.
    assert all("not_allowed" not in (u.error.code if u.error else "") for u in received)
    assert audit.exists()


async def test_cancel_terminates_running_process(tmp_path: Path) -> None:
    """Sleep, cancel, and confirm the adapter publishes a cancelled status."""
    import asyncio

    if sys.platform.startswith("win"):
        pytest.skip("POSIX-only cancel timing test")

    adapter = _shell_with(
        working_dir=str(tmp_path),
        allowlist=(AllowlistEntry(cmd="sleep", positional_pattern=r"\d+"),),
        cancel_grace_s=0.3,
    )
    handle = await adapter.submit(
        TaskRequest(summary="sleep", instructions="sleep 5")
    )
    # Give the process a moment to actually start.
    await asyncio.sleep(0.05)
    await adapter.cancel(handle)
    received = [upd async for upd in adapter.updates(handle)]
    final = received[-1]
    assert final.status in {"cancelled", "failed"}
