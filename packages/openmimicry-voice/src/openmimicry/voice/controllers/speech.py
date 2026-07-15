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
import re
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
    WakeDetected,
)
from openmimicry.core.schemas.app import VoiceConfig

__all__ = ["SpeechController", "make_speech_controller"]


_log = logging.getLogger(__name__)
_PTT_FINAL_TIMEOUT_SECONDS = 8.0


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
        self._listening_mode: str | None = None
        self._configured_wake_names: list[str] = _normalise_wake_names(self._cfg.stt.wake.names)
        self._live_wake_names: list[str] = []
        self._resume_listening_after_ptt: tuple[str, list[str]] | None = None
        self._started: bool = False

    @property
    def is_speaking(self) -> bool:
        return self._tts.is_speaking

    @property
    def live_listening(self) -> bool:
        return self._live_listening

    @property
    def continuous_listening(self) -> bool:
        return self._live_listening and self._listening_mode == "continuous"

    @property
    def listening_mode(self) -> str:
        if self._ptt_active:
            return "push_to_talk"
        return self._listening_mode or "off"

    @property
    def ptt_active(self) -> bool:
        return self._ptt_active

    @property
    def wake_names(self) -> list[str]:
        """Configured wake-name prefixes, returned as a defensive copy."""

        return list(self._configured_wake_names)

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
        resume: tuple[str, list[str]] | None = None
        if self._live_listening and self._listening_mode is not None:
            resume = (self._listening_mode, list(self._live_wake_names))
            await self._stop_passive_listening()
        try:
            await self._stt.start(self._dictation_config())
        except Exception:
            if resume is not None:
                await self._restore_passive_listening(resume)
            raise
        self._resume_listening_after_ptt = resume
        self._ptt_active = True
        self._bus.publish(UserSpeechStarted(ts=_now()))

    async def ptt_up(self) -> None:
        """Close dictation STT; publish the next final transcript as the result."""
        if not self._ptt_active:
            return
        # Read the next final transcript (with a short timeout so a noisy
        # tail doesn't deadlock the caller).
        resume = self._resume_listening_after_ptt
        self._resume_listening_after_ptt = None
        try:
            # First-run Whisper model initialization and ordinary Windows CPU
            # transcription can exceed two seconds after the button is
            # released. Keep the microphone turn alive long enough to receive
            # the final transcript instead of silently submitting no speech.
            text, reason = await self._await_final_transcript(timeout_s=_PTT_FINAL_TIMEOUT_SECONDS)
        except Exception:
            with suppress(Exception):
                await self._stt.stop()
            self._ptt_active = False
            if resume is not None:
                await self._restore_passive_listening(resume)
            raise
        with suppress(Exception):
            await self._stt.stop()
        self._ptt_active = False
        self._bus.publish(UserSpeechFinal(ts=_now(), text=text, reason=reason))
        if resume is not None:
            await self._restore_passive_listening(resume)

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

    # --------------------------------------------- continuous / wake listening

    def _dictation_config(self) -> STTConfig:
        return STTConfig(
            language=self._cfg.stt.language,
            mode="dictation",
            wake_names=[],
            sample_rate=self._cfg.stt.sample_rate,
            vad=self._cfg.stt.vad,
        )

    async def enable_continuous_listening(self) -> None:
        """Continuously wait for normal speech; no wake phrase is required."""

        if self._ptt_active:
            self._resume_listening_after_ptt = ("continuous", [])
            return
        if self.continuous_listening:
            return
        if self._live_listening:
            await self._stop_passive_listening()
        await self._start_passive_listening(
            mode="continuous",
            config=self._dictation_config(),
            wake_names=[],
        )

    async def enable_live_listening(self, *, wake_names: list[str] | None = None) -> None:
        """Continuously listen, accepting only commands prefixed by a wake name."""

        names = _normalise_wake_names(
            wake_names if wake_names is not None else self._configured_wake_names
        )
        if not names:
            raise ValueError("wake-name listening requires at least one configured name")
        if self._live_listening and self._listening_mode == "wake":
            return
        if self._ptt_active:
            self._resume_listening_after_ptt = ("wake", list(names))
            return
        if self._live_listening:
            await self._stop_passive_listening()
        await self._start_passive_listening(
            mode="wake",
            wake_names=list(names),
            config=STTConfig(
                language=self._cfg.stt.language,
                mode="wake",
                wake_names=list(names),
                sample_rate=self._cfg.stt.sample_rate,
                vad=self._cfg.stt.vad,
            ),
        )

    async def set_wake_names(self, names: list[str]) -> None:
        """Update wake prefixes and restart an active wake listener safely."""

        normalised = _normalise_wake_names(names)
        if not normalised:
            raise ValueError("at least one non-empty wake name is required")
        self._configured_wake_names = normalised
        if self._resume_listening_after_ptt is not None:
            mode, _old_names = self._resume_listening_after_ptt
            if mode == "wake":
                self._resume_listening_after_ptt = (mode, list(normalised))
        if self._live_listening and self._listening_mode == "wake":
            await self._stop_passive_listening()
            await self.enable_live_listening(wake_names=normalised)

    async def _start_passive_listening(
        self,
        *,
        mode: str,
        config: STTConfig,
        wake_names: list[str],
    ) -> None:
        await self._stt.start(config)
        self._listening_mode = mode
        self._live_wake_names = list(wake_names)
        self._live_listening = True
        self._live_listener_task = asyncio.create_task(
            self._live_listener(), name=f"openmimicry.voice.{mode}_listener"
        )

    async def _restore_passive_listening(self, state: tuple[str, list[str]]) -> None:
        mode, names = state
        if mode == "continuous":
            await self.enable_continuous_listening()
        elif mode == "wake":
            await self.enable_live_listening(wake_names=names)

    async def disable_live_listening(self) -> None:
        """Disable either passive listening mode and cancel any PTT resume."""

        self._resume_listening_after_ptt = None
        await self._stop_passive_listening()

    async def _stop_passive_listening(self) -> None:
        if not self._live_listening:
            self._listening_mode = None
            self._live_wake_names = []
            return
        self._live_listening = False
        self._listening_mode = None
        self._live_wake_names = []
        task = self._live_listener_task
        self._live_listener_task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        with suppress(Exception):
            await self._stt.stop()

    async def _live_listener(self) -> None:
        """Project transcripts while continuous or wake listening is active."""
        wake_announced = False
        try:
            async for transcript in self._stt.transcripts:
                wake_match: tuple[str, str] | None = None
                if self._listening_mode == "wake":
                    wake_match = _extract_wake_command(transcript.text, self._live_wake_names)
                    if wake_match is None:
                        if transcript.is_final:
                            wake_announced = False
                        continue
                    wake_name, command = wake_match
                    if not wake_announced:
                        self._bus.publish(WakeDetected(ts=_now(), name=wake_name))
                        wake_announced = True
                else:
                    command = transcript.text.strip()

                if transcript.is_final:
                    wake_announced = False
                    if command:
                        self._bus.publish(UserSpeechFinal(ts=_now(), text=command, reason="normal"))
                else:
                    if command:
                        self._bus.publish(
                            TranscriptPreview(ts=_now(), text=command, is_final=False)
                        )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.warning("SpeechController._live_listener: %s", exc, exc_info=True)


def _normalise_wake_names(names: list[str]) -> list[str]:
    """Trim, de-duplicate, and prefer the longest prefix during matching."""

    unique: dict[str, str] = {}
    for raw in names:
        name = " ".join(str(raw).split()).strip(" ,.:;!?-")
        if name:
            unique.setdefault(name.casefold(), name)
    return sorted(unique.values(), key=len, reverse=True)


def _extract_wake_command(text: str, names: list[str]) -> tuple[str, str] | None:
    """Return ``(matched_name, command)`` only when ``text`` begins with a name."""

    for name in names:
        match = re.match(
            rf"^\s*{re.escape(name)}(?=$|[\s,.:;!?-])",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        command = text[match.end() :].lstrip(" \t,.:;!?-")
        return name, command
    return None


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
