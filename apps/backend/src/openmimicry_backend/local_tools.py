"""Deterministic, provider-neutral local tools with an explicit safety policy."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import subprocess
import webbrowser
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from openmimicry.core.schemas.app import ToolsConfig

__all__ = ["LocalToolService"]


_URL = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
_SPOTIFY = re.compile(r"^\s*play\s+(.+?)\s+on\s+spotify[.!?]?\s*$", re.IGNORECASE)
_FOLDER = re.compile(r"^\s*open\s+(?:the\s+)?folder\s+(.+?)[.!?]?\s*$", re.IGNORECASE)
_FILE = re.compile(
    r"^\s*(?:write|create|save)\s+(?:a\s+)?(?:text\s+)?file\s+"
    r"(?:called|named)?\s*([\w ._-]+\.txt)\s+(?:with|containing)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_ALARM = re.compile(
    r"^\s*(?:set|create|schedule|defina|crie|agende|configura|crea|programme|règle)\s+"
    r"(?:an?|um|uma|un|une)?\s*(?:alarm|alarme|alarma)\s+"
    r"(?:for|at|to|para|às?|a|à|pour)\s+"
    r"(\d{1,2})(?:(?::|h)(\d{2})?|\s*h)\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_APP = re.compile(r"^\s*(?:open|launch|start)\s+(.+?)[.!?]?\s*$", re.IGNORECASE)


_log = logging.getLogger(__name__)


class LocalToolService:
    """Execute a deliberately small cross-platform tool vocabulary."""

    def __init__(
        self,
        config: ToolsConfig,
        *,
        data_dir: str,
        notify: Callable[[str, str], None] | None = None,
    ) -> None:
        self.config = config
        self._notify = notify
        self._alarms_path = Path(data_dir).expanduser() / "tools" / "alarms.json"
        self._alarm_tasks: set[asyncio.Task[None]] = set()

    def reconfigure(self, config: ToolsConfig) -> None:
        self.config = config

    async def try_execute(self, text: str) -> str | None:
        if not self.config.enabled:
            _log.debug("local tools disabled; falling through to conversation")
            return None
        if self.config.provider == "endpoint":
            payload = await asyncio.to_thread(self._endpoint_execute, text)
            if not isinstance(payload, dict) or not payload.get("handled"):
                _log.info("tool endpoint did not handle request")
                return None
            spoken = payload.get("spoken_reply")
            _log.info("tool endpoint handled request")
            return str(spoken) if isinstance(spoken, str) and spoken.strip() else "Done."
        if match := _SPOTIFY.match(text):
            if not self.config.allow_music:
                return None
            query = match.group(1).strip()
            await asyncio.to_thread(
                webbrowser.open, f"https://open.spotify.com/search/{quote_plus(query)}"
            )
            return f"I opened Spotify search for {query}."
        if self.config.allow_browser and (
            "open" in text.casefold() or "browser" in text.casefold()
        ):
            url = _URL.search(text)
            if url:
                await asyncio.to_thread(webbrowser.open, url.group(0).rstrip(".,;"))
                return "I opened the requested link in your default browser."
        if match := _FILE.match(text):
            if not self.config.allow_files:
                return None
            target = self._safe_output_path(match.group(1))
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with target.open("x", encoding="utf-8", errors="strict") as stream:
                    stream.write(match.group(2).strip())
            except FileExistsError as exc:
                raise ValueError("the requested text file already exists") from exc
            return f"I wrote the requested information to {target.name}."
        if match := _FOLDER.match(text):
            if not self.config.allow_folders:
                return None
            folder = self._safe_existing_path(match.group(1), directory=True)
            await asyncio.to_thread(self._open_path, folder)
            return f"I opened the folder {folder.name}."
        if match := _ALARM.match(text):
            if not self.config.allow_alarms:
                _log.info("alarm request matched but alarms are denied by policy")
                return None
            hour, minute = int(match.group(1)), int(match.group(2) or 0)
            if hour > 23 or minute > 59:
                raise ValueError("alarm time must use 24-hour HH:MM format")
            now = datetime.now().astimezone()
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            self._schedule_alarm(due)
            _log.info("alarm tool scheduled: due=%s", due.isoformat())
            return f"Alarm set for {due.strftime('%H:%M')}."
        if match := _APP.match(text):
            if not self.config.allow_applications:
                return None
            alias = match.group(1).strip().casefold()
            command = self.config.application_aliases.get(alias)
            if not command:
                return None
            await asyncio.create_subprocess_exec(command)
            return f"I launched {alias}."
        _log.info("no deterministic local tool matched; falling through to conversation")
        return None

    def _allowed_roots(self) -> list[Path]:
        return [Path(raw).expanduser().resolve() for raw in self.config.allowed_roots]

    def _endpoint_execute(self, text: str) -> Any:
        request = Request(
            str(self.config.endpoint),
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30.0) as response:
            return json.loads(response.read(1024 * 1024).decode("utf-8"))

    def _safe_output_path(self, raw: str) -> Path:
        roots = self._allowed_roots()
        if not roots:
            raise ValueError("no file output directory is allowed")
        candidate = (roots[0] / Path(raw).name).resolve()
        if roots[0] not in candidate.parents:
            raise ValueError("requested file escapes the allowed directory")
        if candidate.exists():
            raise FileExistsError(candidate)
        return candidate

    def _safe_existing_path(self, raw: str, *, directory: bool) -> Path:
        candidate = Path(raw.strip().strip('"')).expanduser().resolve()
        if not any(
            candidate == root or root in candidate.parents for root in self._allowed_roots()
        ):
            raise ValueError("requested path is outside configured allowed roots")
        if not candidate.exists() or (directory and not candidate.is_dir()):
            raise ValueError("requested local path does not exist")
        return candidate

    @staticmethod
    def _open_path(path: Path) -> None:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _schedule_alarm(self, due: datetime) -> None:
        self._alarms_path.parent.mkdir(parents=True, exist_ok=True)
        alarms: list[dict[str, Any]] = []
        if self._alarms_path.is_file():
            try:
                loaded = json.loads(self._alarms_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    alarms = loaded
            except (OSError, json.JSONDecodeError):
                alarms = []
        alarms.append({"due": due.isoformat(), "created_by": "openmimicry"})
        temporary = self._alarms_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(alarms, indent=2), encoding="utf-8")
        os.replace(temporary, self._alarms_path)
        task = asyncio.create_task(self._wait_alarm(due), name="openmimicry.tool.alarm")
        self._alarm_tasks.add(task)
        task.add_done_callback(self._alarm_tasks.discard)

    async def start(self) -> None:
        """Restore future alarms without duplicating their stored records."""

        if not self._alarms_path.is_file():
            return
        try:
            values = json.loads(self._alarms_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        now = datetime.now().astimezone()
        for item in values if isinstance(values, list) else []:
            try:
                due = datetime.fromisoformat(str(item["due"]))
            except (KeyError, TypeError, ValueError):
                continue
            if due <= now:
                continue
            task = asyncio.create_task(self._wait_alarm(due), name="openmimicry.tool.alarm")
            self._alarm_tasks.add(task)
            task.add_done_callback(self._alarm_tasks.discard)

    async def _wait_alarm(self, due: datetime) -> None:
        await asyncio.sleep(max(0.0, (due - datetime.now().astimezone()).total_seconds()))
        if self._notify:
            self._notify("Alarm", f"Alarm scheduled for {due.strftime('%H:%M')}")

    async def close(self) -> None:
        for task in self._alarm_tasks:
            task.cancel()
        if self._alarm_tasks:
            await asyncio.gather(*self._alarm_tasks, return_exceptions=True)
