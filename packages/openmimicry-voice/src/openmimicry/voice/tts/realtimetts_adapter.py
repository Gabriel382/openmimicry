"""``RealtimeTTSAdapter`` — wraps ``RealtimeTTS.TextToAudioStream``.

RealtimeTTS is import-time heavy and audio-device-bound. We lazy-import it
inside :meth:`speak` so a mocks-only install does not need it.

Engine selection is keyed off ``TTSConfig.engine`` (e.g. ``coqui``,
``piper``, ``openai``, ``azure``). The factory mapping is centralised in
:func:`_build_engine` so M6 / future modules can monkey-patch it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from typing import Any

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
        self._cancel = asyncio.Event()
        self._is_speaking: bool = False
        self._closed: bool = False
        self._engine_name: str | None = None

    async def speak(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        config: TTSConfig,
        on_chunk: OnChunk | None = None,
    ) -> None:
        stream_cls = _import_stream_class()
        engine = _build_engine(config.engine, config.voice or self._settings.voice)
        self._engine_name = config.engine

        self._stream = stream_cls(engine)
        self._cancel.clear()
        self._is_speaking = True

        try:
            if isinstance(text_or_stream, str):
                self._stream.feed(text_or_stream)
            else:
                async for piece in text_or_stream:
                    if self._cancel.is_set():
                        break
                    self._stream.feed(piece)

            if self._cancel.is_set():
                return

            # play_async returns immediately; we poll the is_playing flag
            # to know when the stream finishes, honouring cancellation.
            self._stream.play_async()

            while True:
                if self._cancel.is_set():
                    self._safe_stop()
                    return
                is_playing = bool(getattr(self._stream, "is_playing", lambda: False)())
                if not is_playing:
                    return
                await asyncio.sleep(0.02)
        finally:
            self._is_speaking = False
            self._stream = None

    async def stop(self) -> None:
        self._cancel.set()
        self._safe_stop()
        await asyncio.sleep(0)

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

    def _safe_stop(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:  # noqa: BLE001 — shutdown race
            pass


def _import_stream_class() -> Any:
    try:
        from RealtimeTTS import TextToAudioStream  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RealtimeTTSUnavailable(
            'RealtimeTTS is not installed. Install with `pip install "openmimicry-voice[realtimetts]"`.'
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
