"""Per-utterance Piper synthesis and playback in disposable processes."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import logging
import os
import sys
import tempfile
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openmimicry.core.contracts import OnChunk
from openmimicry.core.schemas import TTSConfig

__all__ = [
    "IsolatedPiperSettings",
    "IsolatedPiperTTSAdapter",
    "IsolatedTTSUnavailable",
    "make_isolated_piper_adapter",
]


_log = logging.getLogger(__name__)


class IsolatedTTSUnavailable(RuntimeError):
    """Raised when Piper, its voice, or an audio output is unavailable."""


@dataclass(frozen=True)
class IsolatedPiperSettings:
    data_dir: str = "~/.openmimicry/voices"
    worker_module: str = "openmimicry.voice.workers.piper_job"
    startup_timeout_s: float = 90.0


class IsolatedPiperTTSAdapter:
    """Synthesize and play one reply in one killable child process."""

    name = "isolated-piper"

    def __init__(self, *, settings: IsolatedPiperSettings | None = None) -> None:
        self._settings = settings or IsolatedPiperSettings()
        self._process: asyncio.subprocess.Process | None = None
        self._ready: asyncio.Event | None = None
        self._is_speaking = False
        self._closed = False
        self._stop_requested = False
        self._turn_lock = asyncio.Lock()
        self._last_error: str | None = None

    @property
    def data_dir(self) -> Path:
        return Path(self._settings.data_dir).expanduser()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def prepare(self, config: TTSConfig) -> None:
        if self._closed:
            raise RuntimeError("isolated Piper adapter is closed")
        if importlib.util.find_spec("piper") is None:
            raise IsolatedTTSUnavailable(
                "Piper is not installed. Run `.\\scripts\\win\\install.bat openrouter-voice`."
            )
        model = self._model_path(config.voice)
        if not model.is_file():
            raise IsolatedTTSUnavailable(
                f"Piper voice {config.voice!r} is not installed in {self.data_dir}. "
                'Run `python -m piper.download_voices --data-dir "%USERPROFILE%\\.openmimicry\\voices" '
                f"{config.voice}`."
            )
        model_config = self._model_config_path(model)
        if not model_config.is_file():
            raise IsolatedTTSUnavailable(
                f"Piper voice configuration is missing: {model_config}. "
                "Download the voice again before enabling audio."
            )

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None:
        if self._closed:
            raise RuntimeError("isolated Piper adapter is closed")
        pieces: list[str] = []
        if isinstance(text_or_stream, str):
            pieces.append(text_or_stream)
        else:
            async for piece in text_or_stream:
                pieces.append(piece)
        text = "".join(pieces).strip()
        if not text:
            return

        async with self._turn_lock:
            await self.prepare(config)
            self._ready = asyncio.Event()
            self._last_error = None
            self._stop_requested = False
            self._is_speaking = True
            with tempfile.TemporaryDirectory(prefix="openmimicry-tts-") as temp_dir:
                output = Path(temp_dir) / "reply.wav"
                args = [
                    sys.executable,
                    "-m",
                    self._settings.worker_module,
                    "--model",
                    str(self._model_path(config.voice)),
                    "--output",
                    str(output),
                    "--rate",
                    str(config.rate),
                ]
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                self._process = process
                assert process.stdin is not None
                process.stdin.write(text.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                try:
                    await self._consume_worker(process)
                except asyncio.CancelledError:
                    await self._terminate_process(process)
                    raise
                finally:
                    if self._process is process:
                        self._process = None
                    self._is_speaking = False
            _ = on_chunk

    async def _consume_worker(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        assert process.stderr is not None
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            while line := await process.stdout.readline():
                try:
                    message = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                event = message.get("event")
                if event == "playback_started":
                    if self._ready is not None:
                        self._ready.set()
                    _log.info(
                        "isolated Piper playback started: duration=%.2fs",
                        float(message.get("duration_s", 0.0)),
                    )
                elif event == "error":
                    self._last_error = str(message.get("message") or "Piper worker failed")
            return_code = await process.wait()
            stderr = (await stderr_task).decode(errors="replace").strip()
            if return_code != 0 and not self._stop_requested:
                detail = self._last_error or stderr or f"Piper worker exited {return_code}"
                raise RuntimeError(detail)
        finally:
            if not stderr_task.done():
                stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stderr_task

    async def wait_until_ready(self, *, timeout_s: float = 30.0) -> bool:
        ready = self._ready
        if ready is None:
            return False
        try:
            await asyncio.wait_for(ready.wait(), timeout=max(0.05, timeout_s))
        except TimeoutError:
            return False
        return True

    async def stop(self) -> None:
        process = self._process
        if process is not None:
            self._stop_requested = True
            await self._terminate_process(process)
        self._is_speaking = False

    async def close(self) -> None:
        if self._closed:
            return
        await self.stop()
        self._closed = True

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def healthcheck(self) -> bool:
        return importlib.util.find_spec("piper") is not None and not self._closed

    async def _terminate_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            process.kill()
            with contextlib.suppress(Exception):
                await process.wait()

    def _model_path(self, voice: str) -> Path:
        raw = Path(voice).expanduser()
        if raw.is_file() or raw.suffix == ".onnx":
            return raw
        return self.data_dir / f"{voice}.onnx"

    @staticmethod
    def _model_config_path(model: Path) -> Path:
        return Path(f"{model}.json")


def make_isolated_piper_adapter(*_args: Any, **_kwargs: Any) -> IsolatedPiperTTSAdapter:
    return IsolatedPiperTTSAdapter()
