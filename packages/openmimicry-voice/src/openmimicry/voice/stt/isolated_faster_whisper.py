"""Crash-contained microphone capture and Faster-Whisper transcription.

The adapter owns no PortAudio handle and no Whisper model in the backend
process.  Both live in a supervised child process that exchanges newline
delimited JSON with this adapter.  A broken audio driver or native inference
runtime can therefore be terminated and recreated without poisoning FastAPI,
WebSockets, TTS, or a later conversation turn.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openmimicry.core.schemas import STTConfig, Transcript

__all__ = [
    "IsolatedFasterWhisperAdapter",
    "IsolatedFasterWhisperSettings",
    "IsolatedSTTUnavailable",
    "make_isolated_faster_whisper_adapter",
]


_log = logging.getLogger(__name__)


class IsolatedSTTUnavailable(RuntimeError):
    """Raised when the isolated input runtime cannot be started."""


@dataclass(frozen=True)
class IsolatedFasterWhisperSettings:
    """Process and inference settings kept outside the stable STT contract."""

    device: str = "auto"
    compute_type: str = "auto"
    beam_size: int = 5
    speech_threshold: float = 0.015
    worker_module: str = "openmimicry.voice.workers.stt_service"
    startup_timeout_s: float = 300.0
    command_timeout_s: float = 120.0


class IsolatedFasterWhisperAdapter:
    """STT adapter backed by one supervised, preloaded worker process."""

    name = "isolated-faster-whisper"

    def __init__(self, *, settings: IsolatedFasterWhisperSettings | None = None) -> None:
        self._settings = settings or IsolatedFasterWhisperSettings()
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[Transcript | None] = asyncio.Queue()
        self._ready: asyncio.Future[dict[str, Any]] | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._command_sequence = 0
        self._signature: tuple[Any, ...] | None = None
        self._started = False
        self._closed = False
        self._vad_active = False
        self._lifecycle_lock = asyncio.Lock()
        self._runtime_info: dict[str, Any] = {}

    @property
    def runtime_info(self) -> dict[str, Any]:
        return dict(self._runtime_info)

    async def prepare(self, config: STTConfig) -> None:
        """Start and warm a worker for ``config`` without opening the microphone."""

        if self._closed:
            raise RuntimeError("isolated STT adapter is closed")
        signature = self._config_signature(config)
        async with self._lifecycle_lock:
            if self._worker_alive and signature == self._signature:
                return
            await self._close_worker()
            await self._spawn_worker(config)
            self._signature = signature

    async def start(self, config: STTConfig) -> None:
        if self._started:
            return
        await self.prepare(config)
        self._drain_transcripts()
        await self._command(
            "start",
            mode=config.mode,
            post_speech_silence_duration=config.post_speech_silence_duration,
        )
        self._started = True
        _log.info(
            "Isolated STT session started: mode=%s model=%s worker_pid=%s",
            config.mode,
            config.model,
            self._process.pid if self._process else None,
        )

    async def finish_utterance(self) -> None:
        if not self._started:
            return
        await self._command("finish")

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._vad_active = False
        try:
            await self._command("stop", timeout_s=5.0)
        except Exception as exc:
            _log.warning("isolated STT stop failed; recycling worker: %s", exc)
            async with self._lifecycle_lock:
                await self._close_worker()
            self._signature = None
        self._queue.put_nowait(None)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._started = False
        async with self._lifecycle_lock:
            process = self._process
            if process is not None and process.returncode is None:
                with contextlib.suppress(Exception):
                    await self._command("shutdown", timeout_s=2.0)
            await self._close_worker()
        self._queue.put_nowait(None)

    @property
    def transcripts(self) -> AsyncIterator[Transcript]:
        return self._iter_transcripts()

    async def _iter_transcripts(self) -> AsyncIterator[Transcript]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    @property
    def vad_active(self) -> bool:
        return self._vad_active

    async def healthcheck(self) -> bool:
        dependencies = all(
            importlib.util.find_spec(module) is not None
            for module in ("faster_whisper", "sounddevice", "numpy")
        )
        return dependencies and not self._closed and (self._process is None or self._worker_alive)

    @property
    def _worker_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def _spawn_worker(self, config: STTConfig) -> None:
        loop = asyncio.get_running_loop()
        self._ready = loop.create_future()
        args = [
            sys.executable,
            "-m",
            self._settings.worker_module,
            "--model",
            config.model,
            "--language",
            config.language,
            "--sample-rate",
            str(config.sample_rate),
            "--device",
            self._settings.device,
            "--compute-type",
            self._settings.compute_type,
            "--beam-size",
            str(self._settings.beam_size),
            "--speech-threshold",
            str(self._settings.speech_threshold),
            "--silence-seconds",
            str(config.post_speech_silence_duration),
        ]
        prompt = ", ".join(config.prompt_terms)
        if prompt:
            args.extend(["--prompt", prompt])
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        self._process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        self._reader_task = asyncio.create_task(
            self._read_worker(), name="openmimicry.voice.isolated_stt.stdout"
        )
        self._stderr_task = asyncio.create_task(
            self._read_stderr(), name="openmimicry.voice.isolated_stt.stderr"
        )
        try:
            ready = await asyncio.wait_for(
                asyncio.shield(self._ready), timeout=self._settings.startup_timeout_s
            )
        except Exception:
            await self._close_worker()
            raise
        self._runtime_info = ready
        _log.info(
            "Isolated STT worker ready: pid=%s model=%s device=%s compute=%s",
            self._process.pid if self._process else None,
            ready.get("model"),
            ready.get("device"),
            ready.get("compute_type"),
        )

    async def _command(
        self,
        command: str,
        *,
        timeout_s: float | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        process = self._process
        if process is None or process.returncode is not None or process.stdin is None:
            raise IsolatedSTTUnavailable("isolated STT worker is not running")
        self._command_sequence += 1
        command_id = self._command_sequence
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        message = {"command": command, "id": command_id, **payload}
        try:
            process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            await process.stdin.drain()
            result = await asyncio.wait_for(
                asyncio.shield(future),
                timeout=timeout_s or self._settings.command_timeout_s,
            )
        except Exception:
            self._pending.pop(command_id, None)
            raise
        if result.get("ok") is not True:
            raise RuntimeError(str(result.get("error") or f"STT {command} failed"))
        return result

    async def _read_worker(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            while line := await process.stdout.readline():
                try:
                    message = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    _log.warning("isolated STT emitted malformed output: %r", line[:200])
                    continue
                event = message.get("event")
                if event == "ready":
                    if self._ready is not None and not self._ready.done():
                        self._ready.set_result(message)
                elif event == "ack":
                    command_id = int(message.get("id", 0))
                    future = self._pending.pop(command_id, None)
                    if future is not None and not future.done():
                        future.set_result(message)
                elif event == "transcript":
                    text = str(message.get("text") or "").strip()
                    self._queue.put_nowait(
                        Transcript(
                            text=text,
                            is_final=bool(message.get("is_final", True)),
                            confidence=message.get("confidence"),
                        )
                    )
                elif event == "vad":
                    self._vad_active = bool(message.get("active"))
                elif event == "error":
                    _log.error("isolated STT worker: %s", message.get("message"))
                elif event in {"runtime", "warning"}:
                    self._runtime_info.update(
                        {
                            "device": message.get("device"),
                            "compute_type": message.get("compute_type"),
                            "fallback_reason": message.get("message"),
                        }
                    )
                    log = _log.info if event == "runtime" else _log.warning
                    log("isolated STT runtime: %s", message.get("message"))
        except asyncio.CancelledError:
            raise
        finally:
            error = IsolatedSTTUnavailable("isolated STT worker exited")
            if self._ready is not None and not self._ready.done():
                self._ready.set_exception(error)
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            self._pending.clear()
            self._vad_active = False
            self._queue.put_nowait(None)

    async def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        while line := await process.stderr.readline():
            _log.info("isolated STT worker stderr: %s", line.decode(errors="replace").rstrip())

    async def _close_worker(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1.5)
            except TimeoutError:
                process.kill()
                with contextlib.suppress(Exception):
                    await process.wait()
        current = asyncio.current_task()
        for task in (self._reader_task, self._stderr_task):
            if task is not None and task is not current:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._reader_task = None
        self._stderr_task = None
        self._vad_active = False

    def _drain_transcripts(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()

    @staticmethod
    def _config_signature(config: STTConfig) -> tuple[Any, ...]:
        return (
            config.model,
            config.language,
            config.sample_rate,
            config.vad,
            config.post_speech_silence_duration,
            tuple(config.prompt_terms),
        )


def make_isolated_faster_whisper_adapter(
    *_args: Any, **_kwargs: Any
) -> IsolatedFasterWhisperAdapter:
    return IsolatedFasterWhisperAdapter()
