"""``RealtimeSTTAdapter`` — wraps ``RealtimeSTT.AudioToTextRecorder``.

RealtimeSTT is import-time heavy and audio-device-bound. We lazy-import it
inside :meth:`start` and :meth:`healthcheck` so a mocks-only install does
not need it.

Threading model
---------------

RealtimeSTT calls our callbacks from its own worker thread. We translate
those callbacks into items pushed onto an ``asyncio.Queue`` that lives on
the adapter's event loop, using ``loop.call_soon_threadsafe`` to hop back
into the loop safely.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openmimicry.core.schemas import STTConfig, Transcript

__all__ = [
    "RealtimeSTTAdapter",
    "RealtimeSTTSettings",
    "RealtimeSTTUnavailable",
    "make_realtimestt_adapter",
]


class RealtimeSTTUnavailable(RuntimeError):
    """Raised when ``RealtimeSTT`` is not installed."""


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealtimeSTTSettings:
    """Adapter-level configuration.

    These map onto RealtimeSTT's ``AudioToTextRecorder`` constructor kwargs.
    Only the most common options are surfaced; extra kwargs go in ``extra``.
    """

    model: str = "small.en"
    realtime_model_type: str = "small.en"
    use_main_model_for_realtime: bool = True
    language: str = "en"
    # CPU/int8 is the portable default. RealtimeSTT currently defaults to
    # CUDA, which fails on ordinary Windows machines without a CUDA runtime.
    device: str = "cpu"
    compute_type: str = "int8"
    sample_rate: int = 16000
    use_microphone: bool = True
    enable_realtime_transcription: bool = True
    silero_sensitivity: float = 0.4
    webrtc_sensitivity: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


class RealtimeSTTAdapter:
    """STTAdapter backed by RealtimeSTT's ``AudioToTextRecorder``."""

    name: str = "realtimestt"

    def __init__(
        self,
        *,
        settings: RealtimeSTTSettings | None = None,
    ) -> None:
        self._settings = settings or RealtimeSTTSettings()
        self._recorder: Any = None
        self._queue: asyncio.Queue[Transcript | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._vad_active: bool = False
        self._started: bool = False
        self._closed: bool = False
        self._active_signature: tuple[Any, ...] | None = None
        self._prepare_lock = asyncio.Lock()
        self._session_active = threading.Event()
        self._shutdown = threading.Event()
        self._pump_thread: threading.Thread | None = None

    # ------------------------------------------------------------- Protocol

    async def start(self, config: STTConfig) -> None:
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        await self.prepare(config)
        # Drain any leftover sentinel from a previous run.
        while not self._queue.empty():
            self._queue.get_nowait()

        recorder = self._recorder
        if recorder is None:  # pragma: no cover - defensive
            raise RuntimeError("RealtimeSTT recorder was not prepared")
        self._started = True
        self._closed = False
        self._set_microphone(recorder, True)
        self._session_active.set()
        _log.info(
            "STT session started: mode=%s model=%s recorder=%s",
            config.mode,
            config.model,
            id(recorder),
        )

    async def prepare(self, config: STTConfig) -> None:
        """Load Whisper/VAD once without opening an active listening turn.

        RealtimeSTT model construction is the expensive part of the first PTT
        press.  Keeping the recorder warm also prevents repeated model and
        subprocess churn when TTS temporarily pauses the microphone.
        """

        self._loop = asyncio.get_running_loop()
        signature = self._config_signature(config)
        if self._recorder is not None and signature == self._active_signature:
            return
        async with self._prepare_lock:
            if self._recorder is not None and signature == self._active_signature:
                return
            await asyncio.to_thread(self._replace_recorder, config, signature)

    def _replace_recorder(self, config: STTConfig, signature: tuple[Any, ...]) -> None:
        old = self._recorder
        if old is not None:
            _log.info("STT recorder replacing: old=%s", id(old))
            self._shutdown.set()
            self._session_active.set()
            with contextlib.suppress(Exception):
                old.stop()
            with contextlib.suppress(Exception):
                old.shutdown()
            thread = self._pump_thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=1.0)

        recorder_cls = _import_recorder_class()
        self._shutdown = threading.Event()
        self._session_active = threading.Event()
        kwargs = self._recorder_kwargs(config)
        recorder = recorder_cls(**kwargs)
        self._recorder = recorder
        self._active_signature = signature
        self._set_microphone(recorder, False)
        _log.info(
            "STT recorder prepared: recorder=%s model=%s realtime_model=%s",
            id(recorder),
            config.model,
            config.realtime_model_type,
        )

        def _pump_finals() -> None:
            while not self._shutdown.is_set():
                if not self._session_active.wait(timeout=0.1):
                    continue
                if self._shutdown.is_set():
                    return
                try:
                    text = recorder.text()  # blocks until a final transcript
                except Exception:
                    if self._shutdown.is_set():
                        return
                    self._shutdown.wait(0.05)
                    continue
                if text and self._started:
                    _log.info("STT final received: chars=%d", len(text))
                    self._post(Transcript(text=text, is_final=True))
                elif not text:
                    # Some versions return an empty string when ``stop`` is
                    # used to pause the microphone. Avoid a hot worker loop.
                    self._shutdown.wait(0.03)

        self._pump_thread = threading.Thread(
            target=_pump_finals,
            name="openmimicry.voice.realtimestt",
            daemon=True,
        )
        self._pump_thread.start()

    def _recorder_kwargs(self, config: STTConfig) -> dict[str, Any]:
        """Map the stable OpenMimicry schema to RealtimeSTT kwargs."""

        # Map STTConfig + RealtimeSTTSettings -> AudioToTextRecorder kwargs.
        vad_kwargs: dict[str, Any] = {}
        if config.vad == "silero":
            vad_kwargs["silero_sensitivity"] = self._settings.silero_sensitivity
        elif config.vad == "webrtc":
            vad_kwargs["webrtc_sensitivity"] = self._settings.webrtc_sensitivity

        prompt_names = ", ".join(config.prompt_terms or config.wake_names)
        initial_prompt = (
            f"The desktop assistant wake names are: {prompt_names}." if prompt_names else None
        )
        kwargs: dict[str, Any] = {
            "model": config.model or self._settings.model,
            "realtime_model_type": (
                config.realtime_model_type or self._settings.realtime_model_type
            ),
            "use_main_model_for_realtime": config.use_main_model_for_realtime,
            "language": config.language or self._settings.language,
            "device": self._settings.device,
            "compute_type": self._settings.compute_type,
            "sample_rate": config.sample_rate or self._settings.sample_rate,
            "post_speech_silence_duration": config.post_speech_silence_duration,
            "use_microphone": self._settings.use_microphone,
            "enable_realtime_transcription": self._settings.enable_realtime_transcription,
            "on_realtime_transcription_update": self._on_partial,
            "on_recording_start": self._on_recording_start,
            "on_recording_stop": self._on_recording_stop,
            **vad_kwargs,
            **self._settings.extra,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
            kwargs["initial_prompt_realtime"] = initial_prompt
        # Wake-name matching intentionally happens on normalized transcripts
        # in SpeechController. RealtimeSTT's native wake-word vocabulary is
        # backend-specific and cannot reliably support arbitrary user names.
        return kwargs

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        rec = self._recorder
        self._session_active.clear()
        if rec is not None:
            self._set_microphone(rec, False)
            # ``stop()`` is a manual end-of-utterance signal in RealtimeSTT.
            # Using it for an ordinary pause can leave older releases' text()
            # loop in a terminal state. ``abort()`` cancels the current wait
            # while keeping the preloaded recorder reusable for the next turn.
            self._abort_recorder(rec)
        _log.info("STT session paused: recorder=%s", id(rec) if rec is not None else None)
        # Drop a sentinel so any pending iterator exits.
        self._post(None)

    async def finish_utterance(self) -> None:
        """Ask RealtimeSTT to finalize the current PTT recording immediately."""

        rec = self._recorder
        if rec is not None and self._started:
            _log.info("STT manual utterance finalization requested: recorder=%s", id(rec))
            with contextlib.suppress(Exception):
                rec.stop()

    async def close(self) -> None:
        """Release the preloaded recorder during application shutdown."""

        self._started = False
        self._closed = True
        self._shutdown.set()
        self._session_active.set()
        rec = self._recorder
        self._recorder = None
        if rec is not None:
            with contextlib.suppress(Exception):
                rec.stop()
            with contextlib.suppress(Exception):
                rec.shutdown()
        _log.info("STT recorder closed: recorder=%s", id(rec) if rec is not None else None)
        self._post(None)

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
        try:
            _import_recorder_class()
        except RealtimeSTTUnavailable:
            return False
        return not self._closed

    # -------------------------------------------------------------- callbacks

    def _on_partial(self, text: str) -> None:
        if not text or not self._started:
            return
        self._post(Transcript(text=text, is_final=False))

    def _on_recording_start(self) -> None:
        self._vad_active = True

    def _on_recording_stop(self) -> None:
        self._vad_active = False

    # ------------------------------------------------------------------ util

    def _post(self, item: Transcript | None) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            # Lifecycle calls run on the owning loop. Queue their sentinel
            # immediately so a stop/start pair cannot drain the queue before
            # a deferred sentinel arrives and terminates the new session.
            self._enqueue_item(item)
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._enqueue_item, item)

    def _enqueue_item(self, item: Transcript | None) -> None:
        """Coalesce realtime previews while giving finals strict priority.

        RealtimeSTT can emit partial updates faster than the event bus and
        several desktop WebSockets can render them.  An unbounded FIFO then
        left a completed utterance behind hundreds of obsolete previews, so
        live mode appeared to transcribe forever.  Keep every final, retain at
        most the newest partial, and make a stop sentinel terminal.
        """

        finals: list[Transcript] = []
        stopped = False
        while not self._queue.empty():
            queued = self._queue.get_nowait()
            if queued is None:
                stopped = True
            elif queued.is_final:
                finals.append(queued)

        if item is None:
            self._queue.put_nowait(None)
            return

        for final in finals:
            self._queue.put_nowait(final)
        if stopped:
            self._queue.put_nowait(None)
            return
        self._queue.put_nowait(item)
        if item.is_final:
            _log.info(
                "STT final queued for speech consumer: pending=%d",
                self._queue.qsize(),
            )

    @staticmethod
    def _set_microphone(recorder: Any, enabled: bool) -> None:
        setter = getattr(recorder, "set_microphone", None)
        if callable(setter):
            with contextlib.suppress(Exception):
                setter(enabled)

    @staticmethod
    def _abort_recorder(recorder: Any) -> None:
        abort = getattr(recorder, "abort", None)
        if callable(abort):
            with contextlib.suppress(Exception):
                abort()
            return
        # Compatibility with RealtimeSTT versions that predate abort().
        stop = getattr(recorder, "stop", None)
        if callable(stop):
            with contextlib.suppress(Exception):
                stop()

    def _config_signature(self, config: STTConfig) -> tuple[Any, ...]:
        return (
            config.model,
            config.realtime_model_type,
            config.use_main_model_for_realtime,
            config.language,
            config.sample_rate,
            config.vad,
            config.post_speech_silence_duration,
            tuple(config.prompt_terms),
        )


def _import_recorder_class() -> Any:
    """Lazy-import ``RealtimeSTT.AudioToTextRecorder`` with a typed error."""
    try:
        from RealtimeSTT import AudioToTextRecorder  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RealtimeSTTUnavailable(
            "RealtimeSTT is not installed in OpenMimicry's .venv. Run "
            "`.\\scripts\\win\\install.bat openrouter-voice` from the repository root."
        ) from exc
    return AudioToTextRecorder


def make_realtimestt_adapter(*_args: Any, **_kwargs: Any) -> RealtimeSTTAdapter:
    """Entry-point factory used by the contract conftest."""
    return RealtimeSTTAdapter()
