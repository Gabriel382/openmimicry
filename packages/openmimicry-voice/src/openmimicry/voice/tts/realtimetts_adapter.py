"""``RealtimeTTSAdapter`` — wraps ``RealtimeTTS.TextToAudioStream``.

RealtimeTTS is import-time heavy and audio-device-bound. We lazy-import it
inside :meth:`speak` so a mocks-only install does not need it.

Engine selection is keyed off ``TTSConfig.engine`` (e.g. ``coqui``,
``piper``, ``openai``, ``azure``). The factory mapping is centralised in
:func:`_build_engine` so M6 / future modules can monkey-patch it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import time
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from openmimicry.core.contracts import OnChunk
from openmimicry.core.schemas import TTSConfig

__all__ = [
    "RealtimeTTSAdapter",
    "RealtimeTTSSettings",
    "RealtimeTTSUnavailable",
    "make_realtimetts_adapter",
]


class RealtimeTTSUnavailable(RuntimeError):
    """Raised when ``RealtimeTTS`` is not installed."""


_log = logging.getLogger(__name__)
_STOP_CALL_TIMEOUT_SECONDS = 0.35
_WORKER_DRAIN_TIMEOUT_SECONDS = 2.0


_WorkerJob: TypeAlias = tuple[
    asyncio.AbstractEventLoop,
    asyncio.Future[Any],
    Callable[..., Any],
    tuple[Any, ...],
]


class _DaemonWorkerLane:
    """One replaceable daemon worker for Windows COM-bound TTS operations."""

    def __init__(self, name: str) -> None:
        self._jobs: queue.Queue[_WorkerJob | None] = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(
        self,
        loop: asyncio.AbstractEventLoop,
        function: Callable[..., Any],
        *args: Any,
    ) -> asyncio.Future[Any]:
        if self._closed:
            raise RuntimeError("TTS worker lane is closed")
        future = loop.create_future()
        self._jobs.put((loop, future, function, args))
        return future

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._jobs.put(None)

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            loop, future, function, args = job
            try:
                result = function(*args)
            except BaseException as exc:
                self._post_result(loop, future, error=exc)
            else:
                self._post_result(loop, future, result=result)

    @staticmethod
    def _post_result(
        loop: asyncio.AbstractEventLoop,
        future: asyncio.Future[Any],
        *,
        result: Any = None,
        error: BaseException | None = None,
    ) -> None:
        if loop.is_closed():
            return

        def _settle() -> None:
            if future.done():
                return
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)

        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(_settle)


@dataclass(frozen=True)
class RealtimeTTSSettings:
    """Adapter-level configuration."""

    voice: str = "en_female_1"
    rate: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


class RealtimeTTSAdapter:
    """TTSAdapter backed by RealtimeTTS's ``TextToAudioStream``."""

    name: str = "realtimetts"

    def __init__(self, *, settings: RealtimeTTSSettings | None = None) -> None:
        self._settings = settings or RealtimeTTSSettings()
        self._stream: Any = None
        # Playback runs in a worker thread; this remains safe to set/read
        # across the async-loop/worker boundary.
        self._cancel = threading.Event()
        self._is_speaking: bool = False
        self._closed: bool = False
        self._engine_name: str | None = None
        # SystemEngine uses Windows COM.  Constructing it once and executing
        # every playback on this same worker fixes the common "first reply
        # speaks, later replies are silent" failure caused by changing COM
        # apartments and repeatedly regenerating SpeechLib wrappers.
        self._executor = _DaemonWorkerLane("openmimicry.realtimetts")
        self._engine: Any = None
        self._engine_key: tuple[str, str] | None = None
        self._ready: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._turn_lock = asyncio.Lock()
        self._play_future: asyncio.Future[None] | None = None
        self._turn_number = 0
        self._active_turn: int | None = None
        self._stop_attempts: dict[int, tuple[threading.Thread, threading.Event]] = {}

    async def prepare(self, config: TTSConfig) -> None:
        """Preload the selected TTS engine on its dedicated worker."""

        if self._closed:
            raise RuntimeError("RealtimeTTSAdapter is closed")
        loop = asyncio.get_running_loop()
        await self._executor.submit(
            loop,
            self._ensure_engine,
            config.engine,
            config.voice or self._settings.voice,
        )

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None:
        if self._closed:
            raise RuntimeError("RealtimeTTSAdapter is closed")

        # RealtimeTTS engines and streams are not concurrency-safe. Keep one
        # explicit lane and, critically, do not let cancellation abandon a
        # still-running executor job. An abandoned first play() permanently
        # occupied the single Windows COM worker and every later reply queued
        # behind it.
        async with self._turn_lock:
            self._turn_number += 1
            turn_number = self._turn_number
            started_at = time.monotonic()
            self._engine_name = config.engine
            cancel_event = threading.Event()
            self._cancel = cancel_event
            self._is_speaking = True
            self._active_turn = turn_number
            turn_loop = asyncio.get_running_loop()
            turn_ready = asyncio.Event()
            self._loop = turn_loop
            self._ready = turn_ready
            worker: asyncio.Future[None] | None = None
            stream: Any = None

            try:
                pieces: list[str] = []
                if isinstance(text_or_stream, str):
                    pieces.append(text_or_stream)
                else:
                    async for piece in text_or_stream:
                        if cancel_event.is_set():
                            break
                        pieces.append(piece)

                if cancel_event.is_set() or not any(pieces):
                    return

                await self.prepare(config)
                _log.info(
                    "TTS turn %d queued: engine=%s chars=%d",
                    turn_number,
                    config.engine,
                    sum(len(piece) for piece in pieces),
                )

                def _play_blocking() -> None:
                    nonlocal stream
                    if cancel_event.is_set():
                        return
                    stream_cls = _import_stream_class()
                    engine = self._ensure_engine(
                        config.engine, config.voice or self._settings.voice
                    )
                    if cancel_event.is_set():
                        return

                    def _audio_started() -> None:
                        _log.info("TTS turn %d audio started", turn_number)
                        if not turn_loop.is_closed():
                            turn_loop.call_soon_threadsafe(turn_ready.set)

                    def _audio_stopped() -> None:
                        _log.info("TTS turn %d audio stopped", turn_number)

                    try:
                        stream = stream_cls(
                            engine,
                            on_audio_stream_start=_audio_started,
                            on_audio_stream_stop=_audio_stopped,
                        )
                        has_start_callback = True
                    except TypeError:
                        # RealtimeTTS releases before the callback parameters
                        # are still supported; readiness then means play() was
                        # invoked, which is the strongest signal they expose.
                        stream = stream_cls(engine)
                        has_start_callback = False
                    if self._active_turn == turn_number:
                        self._stream = stream
                    for piece in pieces:
                        if cancel_event.is_set():
                            return
                        stream.feed(piece)
                    if cancel_event.is_set():
                        return
                    if not has_start_callback:
                        _audio_started()
                    stream.play()

                loop = asyncio.get_running_loop()
                worker = self._executor.submit(loop, _play_blocking)
                self._play_future = worker
                # shield() prevents Task.cancel() from marking the executor
                # Future cancelled while the underlying thread keeps running.
                await asyncio.shield(worker)
                _log.info(
                    "TTS turn %d completed in %.2fs",
                    turn_number,
                    time.monotonic() - started_at,
                )
                _ = on_chunk
            except asyncio.CancelledError:
                cancel_event.set()
                await self._stop_stream_bounded(stream, turn_number=turn_number)
                if worker is not None:
                    drained = await self._drain_worker(worker, turn_number=turn_number)
                    if not drained:
                        self._rotate_worker_lane(turn_number=turn_number)
                _log.info("TTS turn %d interrupted", turn_number)
                raise
            finally:
                if self._active_turn == turn_number:
                    self._is_speaking = False
                    self._stream = None
                    self._active_turn = None
                    if self._cancel is cancel_event:
                        self._cancel = threading.Event()
                    if self._play_future is worker:
                        self._play_future = None

    async def stop(self) -> None:
        self._cancel.set()
        await self._stop_stream_bounded(self._stream, turn_number=self._active_turn)

    async def wait_until_ready(self, *, timeout_s: float = 10.0) -> bool:
        ready = self._ready
        if ready is None:
            return False
        try:
            await asyncio.wait_for(ready.wait(), timeout=max(0.05, timeout_s))
        except TimeoutError:
            return False
        return True

    async def close(self) -> None:
        if self._closed:
            return
        await self.stop()
        self._closed = True

        def _close_engine() -> None:
            engine = self._engine
            self._engine = None
            self._engine_key = None
            close = getattr(engine, "shutdown", None) or getattr(engine, "close", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    close()

        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(_WORKER_DRAIN_TIMEOUT_SECONDS):
                await self._executor.submit(loop, _close_engine)
        except TimeoutError:
            _log.error("TTS engine close timed out; abandoning daemon worker lane")
        finally:
            self._executor.close()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def healthcheck(self) -> bool:
        try:
            _import_stream_class()
        except RealtimeTTSUnavailable:
            return False
        return not self._closed

    # ------------------------------------------------------------------ util

    @staticmethod
    def _safe_stop(stream: Any) -> None:
        if stream is None:
            return
        with contextlib.suppress(Exception):
            stream.stop()

    async def _stop_stream_bounded(
        self,
        stream: Any,
        *,
        turn_number: int | None,
    ) -> bool:
        """Run third-party ``stream.stop()`` away from the asyncio loop.

        Some RealtimeTTS/SystemEngine combinations block inside immediate
        playback shutdown.  Calling that method on the event-loop thread froze
        STT, WebSockets, and every later text turn.  A daemon helper plus a
        bounded wait contains that library/device failure without making the
        application unresponsive.
        """

        if stream is None:
            return True
        key = id(stream)
        attempt = self._stop_attempts.get(key)
        if attempt is None or not attempt[0].is_alive():
            done = threading.Event()

            def _request_stop() -> None:
                try:
                    self._safe_stop(stream)
                finally:
                    done.set()

            thread = threading.Thread(
                target=_request_stop,
                name=f"openmimicry.realtimetts.stop.{turn_number or 0}",
                daemon=True,
            )
            self._stop_attempts[key] = (thread, done)
            thread.start()
        else:
            thread, done = attempt

        deadline = time.monotonic() + _STOP_CALL_TIMEOUT_SECONDS
        while not done.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        if done.is_set():
            if self._stop_attempts.get(key) == (thread, done):
                self._stop_attempts.pop(key, None)
            return True
        _log.error(
            "TTS turn %s stop call exceeded %.2fs; continuing recovery off-loop",
            turn_number if turn_number is not None else "unknown",
            _STOP_CALL_TIMEOUT_SECONDS,
        )
        return False

    async def _drain_worker(self, worker: asyncio.Future[None], *, turn_number: int) -> bool:
        """Wait for a stopped playback worker before accepting another turn."""

        try:
            async with asyncio.timeout(_WORKER_DRAIN_TIMEOUT_SECONDS):
                await asyncio.shield(worker)
        except TimeoutError:
            _log.error(
                "TTS turn %d worker did not stop within %.1fs",
                turn_number,
                _WORKER_DRAIN_TIMEOUT_SECONDS,
            )
            return False
        except Exception as exc:
            _log.warning("TTS turn %d worker stopped with error: %s", turn_number, exc)
        return True

    def _rotate_worker_lane(self, *, turn_number: int) -> None:
        """Replace a poisoned COM executor so a later reply is not queued behind it."""

        old_executor = self._executor
        old_executor.close()
        self._executor = _DaemonWorkerLane(f"openmimicry.realtimetts.recovery{turn_number}")
        # The old engine belongs to the old worker's COM apartment.  It must
        # never be reused on the replacement lane.
        self._engine = None
        self._engine_key = None
        _log.error("TTS turn %d worker lane replaced after failed stop", turn_number)

    def _ensure_engine(self, engine_name: str, voice: str) -> Any:
        key = ((engine_name or "system").casefold(), voice or self._settings.voice)
        if self._engine is not None and self._engine_key == key:
            return self._engine
        previous = self._engine
        close = getattr(previous, "shutdown", None) or getattr(previous, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()
        self._engine = _build_engine(engine_name, voice)
        self._engine_key = key
        return self._engine


def _import_stream_class() -> Any:
    try:
        from RealtimeTTS import TextToAudioStream  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RealtimeTTSUnavailable(
            "RealtimeTTS is not installed in OpenMimicry's .venv. Run "
            "`.\\scripts\\win\\install.bat openrouter-voice` from the repository root."
        ) from exc
    return TextToAudioStream


def _build_engine(engine_name: str, voice: str) -> Any:
    """Resolve an engine class for the requested name.

    Lazy-imports each engine so users only pay the cost of the engines they
    actually pick. The mapping is intentionally permissive — unknown engines
    fall back to ``SystemEngine`` so dev workstations always have a working
    fallback.
    """
    try:
        from RealtimeTTS import SystemEngine  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RealtimeTTSUnavailable(str(exc)) from exc

    name = (engine_name or "system").lower()
    if name == "coqui":
        try:
            from RealtimeTTS import CoquiEngine  # type: ignore[import-not-found]

            return CoquiEngine(voice=voice)
        except ImportError:
            return SystemEngine()
    if name == "piper":
        try:
            from RealtimeTTS import PiperEngine  # type: ignore[import-not-found]

            return PiperEngine(voice=voice)
        except ImportError:
            return SystemEngine()
    if name == "azure":
        try:
            from RealtimeTTS import AzureEngine  # type: ignore[import-not-found]

            return AzureEngine(voice=voice)
        except ImportError:
            return SystemEngine()
    if name == "openai":
        try:
            from RealtimeTTS import OpenAIEngine  # type: ignore[import-not-found]

            return OpenAIEngine(voice=voice)
        except ImportError:
            return SystemEngine()
    return SystemEngine()


def make_realtimetts_adapter(*_args: Any, **_kwargs: Any) -> RealtimeTTSAdapter:
    """Entry-point factory used by the contract conftest."""
    return RealtimeTTSAdapter()
