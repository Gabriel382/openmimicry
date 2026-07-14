"""``SpeechController`` — owns the single active TTS task and the barge-in policy.

Invariants (from ``docs/voice_modes.md``):

1. ``SpeechController`` is the **only** code that calls ``tts.stop()``. The
   avatar director does not. The LLM does not. The backend does not.
2. At most one TTS task is alive at any moment. ``say()`` cancels the
   previous before starting the next.
3. Barge-in waits ``voice.modes.barge_in_grace_ms`` before cancelling TTS,
   then re-checks ``stt.vad_active``. If VAD persists, ``interrupt()`` is
   called and ``TTSInterrupted`` is published.

The controller publishes the canonical ``RuntimeEvent`` sequence on the
provided ``EventBus`` so any subscriber (avatar director, frontend
projection, logging tap) sees the same view.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from openmimicry.core.bus import EventBus
from openmimicry.core.contracts import STTAdapter, TTSAdapter
from openmimicry.core.schemas import (
    STTConfig,
    TranscriptPreview,
    TTSConfig,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
)
from openmimicry.core.schemas.app import VoiceConfig

__all__ = ["SpeechController", "make_speech_controller"]


_log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SpeechController:
    """Concrete ``SpeechController``.

    Wires an STT adapter, a TTS adapter, the event bus, and the voice
    config together. Tests pass any STTAdapter / TTSAdapter that satisfies
    the Protocol (typically ``MockSTTAdapter`` / ``MockTTSAdapter``).
    """

    def __init__(
        self,
        *,
        stt: STTAdapter,
        tts: TTSAdapter,
        bus: EventBus,
        config: VoiceConfig | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._bus = bus
        self._cfg: VoiceConfig = config or VoiceConfig()

        self._current_tts_task: asyncio.Task[None] | None = None
        self._live_listener_task: asyncio.Task[None] | None = None
        self._barge_in_task: asyncio.Task[None] | None = None
        self._ptt_active: bool = False
        self._live_listening: bool = False
        self._started: bool = False

    @property
    def is_speaking(self) -> bool:
        return self._tts.is_speaking

    @property
    def live_listening(self) -> bool:
        return self._live_listening

    @property
    def stt(self) -> STTAdapter:
        return self._stt

    @property
    def tts(self) -> TTSAdapter:
        return self._tts

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        # Barge-in watcher runs for the controller's lifetime.
        self._barge_in_task = asyncio.create_task(
            self._barge_in_loop(), name="openmimicry.voice.barge_in"
        )

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        await self.disable_live_listening()
        await self.interrupt()
        if self._barge_in_task is not None:
            self._barge_in_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._barge_in_task
            self._barge_in_task = None
        with suppress(Exception):
            await self._stt.stop()

    # --------------------------------------------------------- TTS / barge-in

    async def say(self, text_or_stream: str | AsyncIterable[str]) -> None:
        """Speak ``text_or_stream``. Cancels any in-flight utterance first."""
        await self.interrupt()
        self._current_tts_task = asyncio.create_task(
            self._speak_once(text_or_stream), name="openmimicry.voice.say"
        )

    async def _speak_once(self, text_or_stream: str | AsyncIterable[str]) -> None:
        tts_config = TTSConfig(
            engine=self._cfg.tts.engine,
            voice=self._cfg.tts.voice,
            rate=self._cfg.tts.rate,
            interruptible=self._cfg.tts.interruptible,
        )
        self._bus.publish(TTSStarted(ts=_now()))
        cancelled = False
        try:
            await self._tts.speak(text_or_stream, config=tts_config)
        except asyncio.CancelledError:
            cancelled = True
            with suppress(Exception):
                await self._tts.stop()
            raise
        except Exception as exc:
            _log.warning("SpeechController: tts.speak raised: %s", exc, exc_info=True)
        finally:
            if cancelled:
                self._bus.publish(TTSInterrupted(ts=_now()))
            else:
                self._bus.publish(TTSFinished(ts=_now()))

    async def interrupt(self) -> None:
        """Stop any in-flight TTS task. Idempotent."""
        task = self._current_tts_task
        self._current_tts_task = None
        if task is None or task.done():
            # Even if no task is alive, stop the adapter so its internal
            # state matches (mocks and real adapters both honour this).
            with suppress(Exception):
                await self._tts.stop()
            return
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task

    async def _barge_in_loop(self) -> None:
        """Watch ``stt.vad_active``; interrupt TTS on persisting activity."""
        grace_s = max(0.0, self._cfg.modes.barge_in_grace_ms / 1000.0)
        poll_s = max(0.02, grace_s / 4 if grace_s else 0.05)
        while True:
            try:
                await asyncio.sleep(poll_s)
                if not self._cfg.tts.interruptible:
                    continue
                if not self._tts.is_speaking:
                    continue
                if not self._stt.vad_active:
                    continue
                # Grace period: wait, then re-check.
                if grace_s:
                    await asyncio.sleep(grace_s)
                if not self._tts.is_speaking:
                    continue
                if not self._stt.vad_active:
                    continue
                _log.info("SpeechController: barge-in; interrupting TTS")
                await self.interrupt()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _log.warning("SpeechController.barge_in_loop: %s", exc, exc_info=True)

    # ----------------------------------------------------------------- PTT

    async def ptt_down(self) -> None:
        """Open dictation STT. Stops any in-flight TTS first."""
        if self._ptt_active:
            return
        await self.interrupt()
        await self._stt.start(
            STTConfig(
                language=self._cfg.stt.language,
                mode="dictation",
                wake_names=[],
                sample_rate=self._cfg.stt.sample_rate,
                vad=self._cfg.stt.vad,
            )
        )
        self._ptt_active = True
        self._bus.publish(UserSpeechStarted(ts=_now()))

    async def ptt_up(self) -> None:
        """Close dictation STT; publish the next final transcript as the result."""
        if not self._ptt_active:
            return
        # Read the next final transcript (with a short timeout so a noisy
        # tail doesn't deadlock the caller).
        text, reason = await self._await_final_transcript(timeout_s=2.0)
        with suppress(Exception):
            await self._stt.stop()
        self._ptt_active = False
        self._bus.publish(UserSpeechFinal(ts=_now(), text=text, reason=reason))

    async def _await_final_transcript(self, *, timeout_s: float) -> tuple[str, str]:
        """Drain the STT stream until a final transcript arrives or we time out.

        Returns ``(text, reason)`` matching ``UserSpeechFinal``.
        """
        last_partial = ""
        try:
            async with asyncio.timeout(timeout_s):
                async for transcript in self._stt.transcripts:
                    if transcript.is_final:
                        return transcript.text, "normal"
                    last_partial = transcript.text
                    self._bus.publish(
                        TranscriptPreview(
                            ts=_now(),
                            text=transcript.text,
                            is_final=False,
                        )
                    )
        except TimeoutError:
            return last_partial, "no_speech" if not last_partial else "normal"
        return last_partial, "no_speech" if not last_partial else "normal"

    # --------------------------------------------------------- live wake mode

    async def enable_live_listening(self, *, wake_names: list[str] | None = None) -> None:
        if self._live_listening:
            return
        names = wake_names if wake_names is not None else self._cfg.stt.wake.names
        await self._stt.start(
            STTConfig(
                language=self._cfg.stt.language,
                mode="wake",
                wake_names=list(names),
                sample_rate=self._cfg.stt.sample_rate,
                vad=self._cfg.stt.vad,
            )
        )
        self._live_listening = True
        self._live_listener_task = asyncio.create_task(
            self._live_listener(), name="openmimicry.voice.live_listener"
        )

    async def disable_live_listening(self) -> None:
        if not self._live_listening:
            return
        self._live_listening = False
        task = self._live_listener_task
        self._live_listener_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        with suppress(Exception):
            await self._stt.stop()

    async def _live_listener(self) -> None:
        """Project STT transcripts onto the bus while live-wake is on."""
        try:
            async for transcript in self._stt.transcripts:
                if transcript.is_final:
                    self._bus.publish(
                        UserSpeechFinal(ts=_now(), text=transcript.text, reason="normal")
                    )
                else:
                    self._bus.publish(
                        TranscriptPreview(ts=_now(), text=transcript.text, is_final=False)
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.warning("SpeechController._live_listener: %s", exc, exc_info=True)


def make_speech_controller(*_args: Any, **_kwargs: Any) -> SpeechController:
    """Entry-point factory.

    Building a SpeechController needs a bus + adapters, which the contract
    conftest cannot synthesise. Tests that need a hermetic instance build
    one directly in their fixtures; the entry point is a stub used only
    for Protocol-isinstance assertions on the empty-args path.
    """
    from openmimicry.voice.mocks import MockSTTAdapter, MockTTSAdapter

    return SpeechController(
        stt=MockSTTAdapter(),
        tts=MockTTSAdapter(),
        bus=EventBus(),
    )
