"""Crash-contained, opt-in Chatterbox local voice cloning adapter."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
import tempfile
from collections.abc import AsyncIterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from openmimicry.core.schemas import TTSConfig

from .system_command import _collect_text, _playback_command

__all__ = ["ChatterboxSettings", "ChatterboxTTSAdapter"]


_log = logging.getLogger(__name__)
_MAX_WORKER_MESSAGE_BYTES = 64 * 1024


@dataclass(frozen=True)
class ChatterboxSettings:
    reference_path: str
    consent_record: str
    device: str = "auto"
    startup_timeout_s: float = 180.0


class ChatterboxTTSAdapter:
    """Keep the expensive model warm in one disposable subprocess.

    The model never loads into the FastAPI process. A failed or interrupted
    synthesis discards the worker; the next turn creates a clean replacement.
    """

    name = "chatterbox-local"

    def __init__(self, settings: ChatterboxSettings) -> None:
        self._settings = settings
        self._worker: asyncio.subprocess.Process | None = None
        self._playback: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail = bytearray()
        self._worker_lock = asyncio.Lock()
        self._io_lock = asyncio.Lock()
        self._worker_ready = False
        self._worker_runtime: dict[str, object] = {}
        self._ready = asyncio.Event()
        self._is_speaking = False
        self._synthesizing = False

    def _validate(self) -> Path:
        reference = Path(self._settings.reference_path).expanduser().resolve()
        if not reference.is_file():
            raise RuntimeError(f"Chatterbox reference audio is missing: {reference}")
        if not self._settings.consent_record.strip():
            raise RuntimeError("Chatterbox voice cloning requires an explicit consent record")
        if importlib.util.find_spec("chatterbox") is None:
            raise RuntimeError(
                "Chatterbox is not installed. Install openmimicry-voice[clone-chatterbox]."
            )
        return reference

    async def prepare(self, _config: TTSConfig) -> None:
        self._validate()
        await self._ensure_worker()

    async def _ensure_worker(self) -> asyncio.subprocess.Process:
        async with self._worker_lock:
            worker = self._worker
            if worker is not None and worker.returncode is None and self._worker_ready:
                return worker
            if worker is not None:
                # A live process without a completed ready handshake is not a
                # reusable worker. This can happen when startup is cancelled
                # by shutdown or a bounded caller.
                await self._discard_worker()
            self._stderr_tail.clear()
            self._worker_ready = False
            self._worker_runtime = {}
            worker = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                "openmimicry.voice.workers.chatterbox_job",
                "--server",
                "--device",
                self._settings.device,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._worker = worker
            self._stderr_task = asyncio.create_task(
                self._capture_stderr(worker), name="openmimicry.chatterbox.stderr"
            )
            try:
                message = await self._read_worker_message(
                    worker, timeout_s=self._settings.startup_timeout_s
                )
                if message.get("type") == "error":
                    code = str(message.get("code") or "startup_failed")
                    detail = str(message.get("message") or "unknown worker error")
                    raise RuntimeError(f"Chatterbox worker {code}: {detail[:2000]}")
                if message.get("type") != "ready":
                    raise RuntimeError(f"unexpected Chatterbox startup response: {message}")
                self._worker_runtime = dict(message)
                self._worker_ready = True
                _log.info(
                    "Chatterbox worker ready: device=%s torch=%s cuda=%s "
                    "numpy=%s numpy_compat=%s tokenizer_compat=%s",
                    message.get("device"),
                    message.get("torch_version"),
                    message.get("torch_cuda"),
                    message.get("numpy_version"),
                    message.get("numpy2_compat"),
                    message.get("tokenizer_scalar_compat"),
                )
            except (Exception, asyncio.CancelledError):
                await self._discard_worker()
                raise
            return worker

    async def _capture_stderr(self, worker: asyncio.subprocess.Process) -> None:
        assert worker.stderr is not None
        while chunk := await worker.stderr.read(4096):
            self._stderr_tail.extend(chunk)
            del self._stderr_tail[:-4000]

    async def _read_worker_message(
        self, worker: asyncio.subprocess.Process, *, timeout_s: float
    ) -> dict[str, object]:
        assert worker.stdout is not None
        try:
            async with asyncio.timeout(timeout_s):
                # A few upstream ML libraries still print startup messages to
                # stdout. Ignore bounded non-protocol lines; JSON remains the
                # only accepted control channel.
                for _attempt in range(100):
                    line = await worker.stdout.readline()
                    if not line:
                        detail = self._stderr_tail.decode("utf-8", errors="replace")
                        raise RuntimeError(
                            f"Chatterbox worker exited unexpectedly: {detail[-2000:]}"
                        )
                    if len(line) > _MAX_WORKER_MESSAGE_BYTES:
                        raise RuntimeError("Chatterbox worker response exceeded 64 KiB")
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        _log.debug(
                            "ignored Chatterbox stdout: %s",
                            line.decode("utf-8", errors="replace")[:300],
                        )
                        continue
                    if isinstance(value, dict):
                        return value
                raise RuntimeError("Chatterbox worker emitted too many non-protocol lines")
        except TimeoutError as exc:
            detail = self._stderr_tail.decode("utf-8", errors="replace").strip()
            suffix = f"; worker stderr: {detail[-1000:]}" if detail else ""
            raise RuntimeError(
                f"Chatterbox worker did not respond within {timeout_s:.0f}s{suffix}"
            ) from exc
        raise RuntimeError("Chatterbox worker did not return a protocol message")

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk=None,
    ) -> None:
        text = await _collect_text(text_or_stream)
        if not text.strip():
            return
        if len(text) > 5000:
            raise ValueError("Chatterbox input exceeds 5,000 characters")
        reference = self._validate()
        await self.stop()
        self._ready = asyncio.Event()
        self._is_speaking = True
        try:
            with tempfile.TemporaryDirectory(prefix="openmimicry-chatterbox-") as tmp:
                wave_path = Path(tmp) / "utterance.wav"
                await self._synthesize(text, reference, wave_path)
                command, environment = _playback_command(wave_path)
                self._playback = await asyncio.create_subprocess_exec(
                    *command,
                    env=environment,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._ready.set()
                _stdout, stderr = await self._playback.communicate()
                if self._playback.returncode != 0:
                    raise RuntimeError(
                        "Chatterbox audio playback failed: "
                        + stderr.decode("utf-8", errors="replace")[-1000:]
                    )
        except asyncio.CancelledError:
            await self.stop()
            raise
        finally:
            self._playback = None
            self._is_speaking = False

    async def _synthesize(self, text: str, reference: Path, output: Path) -> None:
        async with self._io_lock:
            worker = await self._ensure_worker()
            assert worker.stdin is not None
            request = {
                "type": "synthesize",
                "text": text,
                "reference": str(reference),
                "output": str(output),
            }
            payload = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
            if len(payload) > _MAX_WORKER_MESSAGE_BYTES:
                raise ValueError("Chatterbox worker request exceeded 64 KiB")
            self._synthesizing = True
            try:
                worker.stdin.write(payload)
                await worker.stdin.drain()
                response = await self._read_worker_message(worker, timeout_s=300.0)
            except (Exception, asyncio.CancelledError):
                await self._discard_worker()
                raise
            finally:
                self._synthesizing = False
            if response.get("type") != "complete" or not output.is_file():
                code = str(response.get("code") or "synthesis_failed")
                message = str(response.get("message") or "unknown synthesis error")
                # Do not reuse model/tokenizer state after any failed
                # generation.  The next turn gets a clean worker instead of
                # inheriting an upstream partial inference state.
                await self._discard_worker()
                raise RuntimeError(f"Chatterbox {code}: {message[:2000]}")

    async def wait_until_ready(self, *, timeout_s: float = 30.0) -> bool:
        try:
            async with asyncio.timeout(timeout_s):
                await self._ready.wait()
            return True
        except TimeoutError:
            return False

    async def stop(self) -> None:
        playback = self._playback
        if playback is not None and playback.returncode is None:
            playback.terminate()
            with suppress(Exception):
                async with asyncio.timeout(2.0):
                    await playback.wait()
            if playback.returncode is None:
                playback.kill()
        if self._synthesizing:
            await self._discard_worker()

    async def _discard_worker(self) -> None:
        worker = self._worker
        self._worker = None
        self._worker_ready = False
        self._worker_runtime = {}
        if worker is not None and worker.returncode is None:
            worker.terminate()
            with suppress(Exception):
                async with asyncio.timeout(3.0):
                    await worker.wait()
            if worker.returncode is None:
                worker.kill()
                with suppress(Exception):
                    await worker.wait()
        stderr_task = self._stderr_task
        self._stderr_task = None
        if stderr_task is not None:
            stderr_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await stderr_task

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def runtime_details(self) -> dict[str, object]:
        """Return non-secret worker diagnostics after a successful handshake."""

        return dict(self._worker_runtime)

    async def healthcheck(self) -> bool:
        try:
            self._validate()
        except RuntimeError:
            return False
        worker = self._worker
        # Health checks must never cold-start a multi-gigabyte ML model. The
        # application startup path owns prewarming and its longer deadline.
        return bool(worker is not None and worker.returncode is None and self._worker_ready)

    async def close(self) -> None:
        await self.stop()
        await self._discard_worker()
