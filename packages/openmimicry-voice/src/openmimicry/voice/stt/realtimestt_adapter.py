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


@dataclass(frozen=True)
class RealtimeSTTSettings:
    """Adapter-level configuration.

    These map onto RealtimeSTT's ``AudioToTextRecorder`` constructor kwargs.
    Only the most common options are surfaced; extra kwargs go in ``extra``.
    """

    model: str = "base.en"
    language: str = "en"
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

    # ------------------------------------------------------------- Protocol

    async def start(self, config: STTConfig) -> None:
        if self._started:
            return
        recorder_cls = _import_recorder_class()
        self._loop = asyncio.get_running_loop()
        # Drain any leftover sentinel from a previous run.
        while not self._queue.empty():
            self._queue.get_nowait()

        # Map STTConfig + RealtimeSTTSettings -> AudioToTextRecorder kwargs.
        vad_kwargs: dict[str, Any] = {}
        if config.vad == "silero":
            vad_kwargs["silero_sensitivity"] = self._settings.silero_sensitivity
        elif config.vad == "webrtc":
            vad_kwargs["webrtc_sensitivity"] = self._settings.webrtc_sensitivity

        wake_kwargs: dict[str, Any] = {}
        if config.mode == "wake" and config.wake_names:
            wake_kwargs["wake_words"] = ",".join(config.wake_names)

        kwargs: dict[str, Any] = {
            "model": self._settings.model,
            "language": config.language or self._settings.language,
            "sample_rate": config.sample_rate or self._settings.sample_rate,
            "use_microphone": self._settings.use_microphone,
            "enable_realtime_transcription": self._settings.enable_realtime_transcription,
            "on_realtime_transcription_update": self._on_partial,
            "on_recording_start": self._on_recording_start,
            "on_recording_stop": self._on_recording_stop,
            **vad_kwargs,
            **wake_kwargs,
            **self._settings.extra,
        }
        self._recorder = recorder_cls(**kwargs)
        # AudioToTextRecorder.text() is blocking + callback-driven. We
        # background a thread that pumps final transcripts via the recorder.
        self._started = True
        self._closed = False
        loop = self._loop
        recorder = self._recorder

        def _pump_finals() -> None:
            while recorder is not None:
                try:
                    text = recorder.text()  # blocking until a final
                except Exception:  # noqa: BLE001 — shutdown race
                    return
                if not text:
                    return
                self._post(Transcript(text=text, is_final=True))

        import threading

        self._pump_thread: threading.Thread = threading.Thread(
            target=_pump_finals, name="openmimicry.voice.realtimestt", daemon=True
        )
        self._pump_thread.start()
        # ``loop`` is captured for thread-safe posting; reference kept alive.
        _ = loop

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        rec = self._recorder
        self._recorder = None
        if rec is not None:
            try:
                rec.stop()
            except Exception:  # noqa: BLE001
                pass
            try:
                rec.shutdown()
            except Exception:  # noqa: BLE001
                pass
        # Drop a sentinel so any pending iterator exits.
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
        if not text:
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
            loop.call_soon_threadsafe(self._queue.put_nowait, item)
        except RuntimeError:
            pass


def _import_recorder_class() -> Any:
    """Lazy-import ``RealtimeSTT.AudioToTextRecorder`` with a typed error."""
    try:
        from RealtimeSTT import AudioToTextRecorder  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RealtimeSTTUnavailable(
            'RealtimeSTT is not installed. Install with `pip install "openmimicry-voice[realtimestt]"`.'
        ) from exc
    return AudioToTextRecorder


def make_realtimestt_adapter(*_args: Any, **_kwargs: Any) -> RealtimeSTTAdapter:
    """Entry-point factory used by the contract conftest."""
    return RealtimeSTTAdapter()
