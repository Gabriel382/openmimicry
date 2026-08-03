"""Unit tests for ClaudeCodeAdapter.

The `claude` CLI is not a test dependency. We stub ``shutil.which`` and
``asyncio.create_subprocess_exec`` so the adapter exercises its full code
path against a synthetic process that streams a scripted stdout.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openmimicry.core.schemas.tasks import TaskRequest
from openmimicry.tasks.adapters.claude_code_adapter import (
    ClaudeCodeAdapter,
    ClaudeCodeSettings,
    ClaudeCodeUnavailable,
)


class _FakeStreamReader:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeStreamWriter:
    def __init__(self) -> None:
        self.written: bytearray = bytearray()
        self.closed: bool = False

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _FakeProcess:
    def __init__(self, stdout_lines: list[str], stderr_lines: list[str], exit_code: int) -> None:
        self.pid = 1234
        self.stdout = _FakeStreamReader(stdout_lines)
        self.stderr = _FakeStreamReader(stderr_lines)
        self.stdin = _FakeStreamWriter()
        self._exit_code = exit_code
        self.killed: bool = False
        self.terminated: bool = False

    async def wait(self) -> int:
        return self._exit_code

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


@pytest.fixture
def fake_proc_factory(monkeypatch: pytest.MonkeyPatch):
    """Returns a callable that installs a `create_subprocess_exec` stub."""
    captured: dict[str, Any] = {}

    def install(*, stdout_lines: list[str], stderr_lines: list[str] = (), exit_code: int = 0):
        proc = _FakeProcess(list(stdout_lines), list(stderr_lines), exit_code)
        captured["proc"] = proc

        async def fake_exec(*argv: str, **kwargs: Any):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        # Also stub which() so the CLI resolves regardless of host PATH.
        monkeypatch.setattr(
            "openmimicry.tasks.adapters.claude_code_adapter.shutil.which",
            lambda _name: "/usr/local/bin/claude",
        )
        return captured

    return install


async def test_unavailable_when_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openmimicry.tasks.adapters.claude_code_adapter.shutil.which",
        lambda _name: None,
    )
    adapter = ClaudeCodeAdapter()
    assert await adapter.healthcheck() is False
    handle = await adapter.submit(TaskRequest(summary="s", instructions="hi"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
    assert "cli_missing" in (received[-1].error.code if received[-1].error else "")


async def test_success_streams_stdout(fake_proc_factory) -> None:
    captured = fake_proc_factory(
        stdout_lines=["Working on it...\n", "Wrote file: utils.py\n"],
        exit_code=0,
    )
    adapter = ClaudeCodeAdapter()
    handle = await adapter.submit(TaskRequest(summary="s", instructions="refactor utils"))
    received = [upd async for upd in adapter.updates(handle)]
    statuses = [u.status for u in received]
    assert "running" in statuses
    assert statuses[-1] == "succeeded"
    # Wrote file was parsed into an artifact on the result.
    result = await adapter.result(handle)
    assert result.status == "succeeded"
    assert any("utils.py" in (a.path or "") for a in result.artifacts)

    # The CLI was spawned with our fake path.
    assert captured["argv"][0] == "/usr/local/bin/claude"
    assert "--input-format" in captured["argv"]
    assert "acceptEdits" in captured["argv"]
    # The prompt was piped via stdin.
    assert b"refactor utils" in captured["proc"].stdin.written


async def test_nonzero_exit_is_failed(fake_proc_factory) -> None:
    fake_proc_factory(
        stdout_lines=[],
        stderr_lines=["Authentication required for this project\n"],
        exit_code=2,
    )
    adapter = ClaudeCodeAdapter()
    handle = await adapter.submit(TaskRequest(summary="s", instructions="x"))
    received = [upd async for upd in adapter.updates(handle)]
    assert received[-1].status == "failed"
    assert received[-1].error is not None
    assert "Authentication required" in received[-1].error.message
    result = await adapter.result(handle)
    assert result.status == "failed"
    assert result.error is not None
    assert "Authentication required" in result.error.message


async def test_env_is_curated(fake_proc_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("UNRELATED_SECRET", "do-not-leak")
    captured = fake_proc_factory(stdout_lines=[], exit_code=0)
    adapter = ClaudeCodeAdapter(settings=ClaudeCodeSettings(auth_mode="api"))
    handle = await adapter.submit(TaskRequest(summary="s", instructions="x"))
    [_ async for _ in adapter.updates(handle)]
    env = captured["kwargs"]["env"]
    assert "ANTHROPIC_API_KEY" in env
    assert "UNRELATED_SECRET" not in env


async def test_settings_extra_args_forwarded(fake_proc_factory) -> None:
    captured = fake_proc_factory(stdout_lines=[], exit_code=0)
    adapter = ClaudeCodeAdapter(settings=ClaudeCodeSettings(cli="claude", extra_args=("--print",)))
    handle = await adapter.submit(TaskRequest(summary="s", instructions="hi"))
    [_ async for _ in adapter.updates(handle)]
    assert "--print" in captured["argv"]


def test_resolve_cli_with_absolute_path_validates_existence(tmp_path) -> None:
    bogus = tmp_path / "claude"
    adapter = ClaudeCodeAdapter(settings=ClaudeCodeSettings(cli=str(bogus)))
    with pytest.raises(ClaudeCodeUnavailable):
        adapter._resolve_cli()  # type: ignore[attr-defined]


def test_windows_cmd_shim_is_wrapped_with_comspec() -> None:
    adapter = ClaudeCodeAdapter()
    argv = adapter._build_command(  # type: ignore[attr-defined]
        r"C:\Users\henri\AppData\Roaming\npm\claude.cmd",
        ("--version",),
        env={"COMSPEC": r"C:\Windows\System32\cmd.exe"},
        windows=True,
    )
    assert argv[:4] == (
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/s",
        "/c",
    )
    assert "claude.cmd" in argv[4]
    assert "--version" in argv[4]


async def test_missing_working_directory_is_actionable(
    fake_proc_factory,
    tmp_path,
) -> None:
    fake_proc_factory(stdout_lines=[], exit_code=0)
    missing = tmp_path / "not-created"
    adapter = ClaudeCodeAdapter(settings=ClaudeCodeSettings(working_dir=str(missing)))
    handle = await adapter.submit(TaskRequest(summary="s", instructions="x"))
    updates = [update async for update in adapter.updates(handle)]
    assert updates[-1].error is not None
    assert updates[-1].error.code == "working_directory_missing"
    assert str(missing) in updates[-1].error.message


async def test_diagnostics_checks_version_and_auth_without_model_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    adapter = ClaudeCodeAdapter(settings=ClaudeCodeSettings(working_dir=str(tmp_path)))
    monkeypatch.setattr(adapter, "_resolve_cli", lambda: "/opt/claude")
    calls: list[tuple[str, ...]] = []

    async def fake_probe(_cli: str, args: tuple[str, ...], *, cwd: str):
        assert cwd == str(tmp_path)
        calls.append(args)
        if args == ("--version",):
            return {"returncode": 0, "output": "2.1.220", "error": ""}
        return {
            "returncode": 0,
            "output": '{"loggedIn":true}',
            "error": "",
        }

    monkeypatch.setattr(adapter, "_probe", fake_probe)

    diagnostics = await adapter.diagnostics()

    assert diagnostics["available"] is True
    assert diagnostics["authenticated"] is True
    assert diagnostics["version"] == "2.1.220"
    assert calls == [("--version",), ("auth", "status")]
