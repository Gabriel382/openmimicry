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
import time
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from openmimicry.core.bus import EventBus
from openmimicry.core.contracts import STTAdapter, TTSAdapter
from openmimicry.core.schemas import (
    STTConfig,
    TranscriptPreview,
    TTSConfig,
    TTSFailed,
    TTSFinished,
    TTSInterrupted,
    TTSQueued,
    TTSReady,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
    WakeDetected,
)
from openmimicry.core.schemas.app import VoiceConfig

__all__ = ["SpeechController", "make_speech_controller"]


_log = logging.getLogger(__name__)
_PTT_FINAL_TIMEOUT_SECONDS = 8.0
_WAKE_DUPLICATE_WINDOW_SECONDS = 2.5
_INTERRUPT_SETTLE_TIMEOUT_SECONDS = 0.15
_TTS_MIN_TIMEOUT_SECONDS = 20.0
_TTS_MAX_TIMEOUT_SECONDS = 120.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _consume_background_task(task: asyncio.Task[None]) -> None:
    """Retrieve a detached cleanup task's terminal exception, if any."""

    with suppress(asyncio.CancelledError, Exception):
        task.result()


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
        self._current_utterance_id: str | None = None
        self._speech_ready: asyncio.Future[bool] | None = None
        self._live_listener_task: asyncio.Task[None] | None = None
        self._barge_in_task: asyncio.Task[None] | None = None
        self._ptt_active: bool = False
        self._live_listening: bool = False
        self._listening_mode: str | None = None
        self._configured_wake_names: list[str] = _normalise_wake_names(self._cfg.stt.wake.names)
        self._configured_wake_aliases: list[str] = _normalise_wake_names(self._cfg.stt.wake.aliases)
        self._live_wake_names: list[str] = []
        self._resume_listening_after_ptt: tuple[str, list[str]] | None = None
        self._started: bool = False
        self._stt_ready: bool = False
        self._tts_ready: bool = False
        self._last_accepted_wake: tuple[str, float] | None = None

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
    def wake_aliases(self) -> list[str]:
        return list(self._configured_wake_aliases)

    @property
    def stt_model(self) -> str:
        return self._cfg.stt.model

    @property
    def post_speech_silence_duration(self) -> float:
        """Seconds of silence required before STT finalises an utterance."""

        return self._cfg.stt.post_speech_silence_duration

    @property
    def speech_readiness_timeout_s(self) -> float:
        """Maximum bounded wait for this profile's first audio frame."""

        return self._cfg.tts.readiness_timeout_s

    @property
    def stt(self) -> STTAdapter:
        return self._stt

    @property
    def tts(self) -> TTSAdapter:
        return self._tts

    @property
    def stt_ready(self) -> bool:
        return self._stt_ready

    @property
    def tts_ready(self) -> bool:
        return self._tts_ready

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        prepare = getattr(self._stt, "prepare", None)
        if callable(prepare):
            # Preload Whisper/VAD now so the first PTT press opens an already
            # warm recognizer. Startup remains explicit about any model error.
            try:
                await cast(Callable[..., Awaitable[Any]], prepare)(
                    self._dictation_config(mode="push_to_talk")
                )
                self._stt_ready = True
            except Exception as exc:
                # Text mode is always available. Voice input can be retried by
                # the next PTT/mode action after installation or device repair.
                self._stt_ready = False
                _log.error("SpeechController: STT preflight failed: %s", exc)
        else:
            self._stt_ready = True
        prepare_tts = getattr(self._tts, "prepare", None)
        if callable(prepare_tts):
            try:
                await cast(Callable[..., Awaitable[Any]], prepare_tts)(
                    TTSConfig(
                        engine=self._cfg.tts.engine,
                        voice=self._cfg.tts.voice,
                        rate=self._cfg.tts.rate,
                        interruptible=self._cfg.tts.interruptible,
                    )
                )
                self._tts_ready = True
            except Exception as exc:
                self._tts_ready = False
                _log.error(
                    "SpeechController: TTS preflight failed; text remains available: %s", exc
                )
        else:
            self._tts_ready = True
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
        for adapter in (self._stt, self._tts):
            close = getattr(adapter, "close", None)
            if callable(close):
                with suppress(Exception):
                    await cast(Callable[..., Awaitable[Any]], close)()

    # --------------------------------------------------------- TTS / barge-in

    async def say(
        self,
        text_or_stream: str | AsyncIterable[str],
        *,
        utterance_id: str | None = None,
    ) -> str:
        """Speak ``text_or_stream``. Cancels any in-flight utterance first."""
        await self.interrupt()
        # Default laptop/speaker operation must not leave STT listening to the
        # avatar's own voice. That caused false barge-in, cancelled replies,
        # growing audio queues, and feedback transcripts. Advanced users can
        # opt back into VAD barge-in explicitly.
        resume: tuple[str, list[str]] | None = None
        if (
            not self._cfg.modes.barge_in_enabled
            and self._live_listening
            and self._listening_mode is not None
        ):
            resume = (self._listening_mode, list(self._live_wake_names))
            await self._stop_passive_listening()
        utterance_id = utterance_id or uuid4().hex
        ready = asyncio.get_running_loop().create_future()
        self._current_utterance_id = utterance_id
        self._speech_ready = ready
        self._bus.publish(TTSQueued(ts=_now(), utterance_id=utterance_id))
        self._current_tts_task = asyncio.create_task(
            self._speak_once(text_or_stream, utterance_id, ready, resume),
            name=f"openmimicry.voice.say.{utterance_id[:8]}",
        )
        return utterance_id

    async def wait_until_speech_ready(
        self, *, timeout_s: float = 10.0, utterance_id: str | None = None
    ) -> bool:
        """Wait until the TTS adapter reports that speaker playback began."""

        if utterance_id is not None and utterance_id != self._current_utterance_id:
            return False
        ready = self._speech_ready
        if ready is None:
            return False
        try:
            async with asyncio.timeout(max(0.05, timeout_s)):
                return bool(await asyncio.shield(ready))
        except TimeoutError:
            _log.error("SpeechController: TTS readiness timed out after %.1fs", timeout_s)
            return False
        except Exception as exc:
            _log.warning("SpeechController: TTS readiness wait failed: %s", exc)
            return False

    async def _speak_once(
        self,
        text_or_stream: str | AsyncIterable[str],
        utterance_id: str,
        ready_future: asyncio.Future[bool],
        resume_listening: tuple[str, list[str]] | None,
    ) -> None:
        tts_config = TTSConfig(
            engine=self._cfg.tts.engine,
            voice=self._cfg.tts.voice,
            rate=self._cfg.tts.rate,
            interruptible=self._cfg.tts.interruptible,
        )
        cancelled = False
        failure_message: str | None = None
        play_task: asyncio.Task[None] | None = None
        try:
            play_task = asyncio.create_task(
                self._tts.speak(text_or_stream, config=tts_config),
                name="openmimicry.voice.tts_adapter",
            )
            # Give the adapter one loop turn to replace its prior readiness
            # Event. Without this, reply two could observe reply one's Event.
            await asyncio.sleep(0)
            waiter = getattr(self._tts, "wait_until_ready", None)
            if callable(waiter):
                ready_task = asyncio.create_task(
                    cast(Callable[..., Awaitable[Any]], waiter)(
                        timeout_s=self._cfg.tts.readiness_timeout_s
                    ),
                    name="openmimicry.voice.tts_ready",
                )
                done, _pending = await asyncio.wait(
                    {ready_task, play_task}, return_when=asyncio.FIRST_COMPLETED
                )
                audio_ready = bool(ready_task.result()) if ready_task in done else False
                if not ready_task.done():
                    ready_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await ready_task
            else:
                audio_ready = True
            self._resolve_speech_ready(ready_future, audio_ready)
            # Speaking is a playback state, not a synthesis/queue state.  A
            # failed or stale TTS job must never replace listening/thinking.
            if audio_ready and self._current_tts_task is asyncio.current_task():
                self._tts_ready = True
                self._bus.publish(TTSReady(ts=_now(), utterance_id=utterance_id))
                self._bus.publish(TTSStarted(ts=_now(), utterance_id=utterance_id))
            elif not audio_ready:
                failure_message = "Text-to-speech playback did not become ready."
            timeout_s = _playback_timeout_seconds(text_or_stream)
            try:
                async with asyncio.timeout(timeout_s):
                    await play_task
            except TimeoutError:
                _log.error(
                    "SpeechController: TTS playback exceeded %.1fs; forcing recovery",
                    timeout_s,
                )
                failure_message = f"Text-to-speech playback exceeded {timeout_s:.1f}s."
                if not play_task.done():
                    play_task.cancel()
                with suppress(Exception):
                    await self._tts.stop()
                with suppress(asyncio.CancelledError, Exception):
                    await play_task
        except asyncio.CancelledError:
            cancelled = True
            if play_task is not None and not play_task.done():
                play_task.cancel()
            with suppress(Exception):
                await self._tts.stop()
            if play_task is not None:
                with suppress(asyncio.CancelledError, Exception):
                    await play_task
            self._resolve_speech_ready(ready_future, False)
            raise
        except Exception as exc:
            self._tts_ready = False
            failure_message = str(exc) or type(exc).__name__
            _log.warning("SpeechController: tts.speak raised: %s", exc, exc_info=True)
            if play_task is not None and not play_task.done():
                play_task.cancel()
            with suppress(Exception):
                await self._tts.stop()
            if play_task is not None:
                with suppress(asyncio.CancelledError, Exception):
                    await play_task
            self._resolve_speech_ready(ready_future, False)
        finally:
            self._resolve_speech_ready(ready_future, False)
            if cancelled:
                self._bus.publish(TTSInterrupted(ts=_now(), utterance_id=utterance_id))
            elif failure_message is not None:
                self._bus.publish(
                    TTSFailed(
                        ts=_now(),
                        utterance_id=utterance_id,
                        message=failure_message,
                    )
                )
            else:
                self._bus.publish(TTSFinished(ts=_now(), utterance_id=utterance_id))
            if self._current_utterance_id == utterance_id:
                self._current_utterance_id = None
                self._current_tts_task = None
                self._speech_ready = None
            if resume_listening is not None and self._started and not self._ptt_active:
                try:
                    await self._restore_passive_listening(resume_listening)
                except Exception as exc:
                    _log.warning(
                        "SpeechController: could not restore listening after TTS: %s",
                        exc,
                        exc_info=True,
                    )

    @staticmethod
    def _resolve_speech_ready(future: asyncio.Future[bool], ready: bool) -> None:
        if future is not None and not future.done():
            future.set_result(ready)

    async def interrupt(self) -> None:
        """Request TTS stop without letting a device driver freeze input.

        Third-party audio shutdown continues in the background when it cannot
        settle within the short PTT latency budget.  The adapter owns the
        bounded worker cleanup and replacement lane.
        """

        task = self._current_tts_task
        self._current_tts_task = None
        self._current_utterance_id = None
        if task is None or task.done():
            # Even if no task is alive, stop the adapter so its internal
            # state matches (mocks and real adapters both honour this).
            with suppress(Exception):
                await self._tts.stop()
            return
        task.cancel()
        try:
            async with asyncio.timeout(_INTERRUPT_SETTLE_TIMEOUT_SECONDS):
                await asyncio.shield(task)
        except TimeoutError:
            _log.warning(
                "SpeechController: TTS interrupt still settling after %.2fs; "
                "voice input will continue while audio cleanup runs",
                _INTERRUPT_SETTLE_TIMEOUT_SECONDS,
            )
            task.add_done_callback(_consume_background_task)
        except (asyncio.CancelledError, Exception):
            pass

    async def _barge_in_loop(self) -> None:
        """Watch ``stt.vad_active``; interrupt TTS on persisting activity."""
        grace_s = max(0.0, self._cfg.modes.barge_in_grace_ms / 1000.0)
        poll_s = max(0.02, grace_s / 4 if grace_s else 0.05)
        while True:
            try:
                await asyncio.sleep(poll_s)
                if not self._cfg.modes.barge_in_enabled:
                    continue
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
            await self._stt.start(self._dictation_config(mode="push_to_talk"))
            self._stt_ready = True
        except Exception:
            self._stt_ready = False
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
            finish_utterance = getattr(self._stt, "finish_utterance", None)
            if callable(finish_utterance):
                await cast(Callable[..., Awaitable[Any]], finish_utterance)()
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
        _log.info("SpeechController: PTT transcript (%s): %r", reason, text)
        self._bus.publish(
            UserSpeechFinal(
                ts=_now(),
                text=text,
                raw_text=text,
                reason=reason,
                accepted=bool(text) and reason == "normal",
                input_mode="push_to_talk",
                rejection_reason=None if text else "empty",
            )
        )
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

    def _dictation_config(self, *, mode: str = "dictation") -> STTConfig:
        return STTConfig(
            language=self._cfg.stt.language,
            model=self._cfg.stt.model,
            realtime_model_type=self._cfg.stt.realtime_model_type,
            use_main_model_for_realtime=self._cfg.stt.use_main_model_for_realtime,
            mode=cast(Any, mode),
            wake_names=[],
            prompt_terms=self._wake_match_phrases(),
            sample_rate=self._cfg.stt.sample_rate,
            vad=self._cfg.stt.vad,
            post_speech_silence_duration=self._cfg.stt.post_speech_silence_duration,
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
            config=self._dictation_config(mode="continuous"),
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
            wake_names=self._wake_match_phrases(names),
            config=STTConfig(
                language=self._cfg.stt.language,
                model=self._cfg.stt.model,
                realtime_model_type=self._cfg.stt.realtime_model_type,
                use_main_model_for_realtime=self._cfg.stt.use_main_model_for_realtime,
                mode="wake",
                wake_names=list(names),
                prompt_terms=self._wake_match_phrases(names),
                sample_rate=self._cfg.stt.sample_rate,
                vad=self._cfg.stt.vad,
                post_speech_silence_duration=self._cfg.stt.post_speech_silence_duration,
            ),
        )

    async def set_wake_names(self, names: list[str], aliases: list[str] | None = None) -> None:
        """Update wake prefixes and restart an active wake listener safely."""

        normalised = _normalise_wake_names(names)
        if not normalised:
            raise ValueError("at least one non-empty wake name is required")
        self._configured_wake_names = normalised
        self._configured_wake_aliases = _normalise_wake_names(aliases or [])
        if self._resume_listening_after_ptt is not None:
            mode, _old_names = self._resume_listening_after_ptt
            if mode == "wake":
                self._resume_listening_after_ptt = (mode, list(normalised))
        if self._live_listening and self._listening_mode == "wake":
            await self._stop_passive_listening()
            await self.enable_live_listening(wake_names=normalised)

    async def set_stt_model(self, model: str) -> None:
        """Switch Whisper quality and immediately warm the selected model."""

        selected = str(model).strip()
        supported = {
            "tiny.en",
            "base.en",
            "small.en",
            "medium.en",
            "distil-large-v3",
            "large-v3",
        }
        if selected not in supported:
            raise ValueError(f"unsupported STT model: {selected}")
        passive_state: tuple[str, list[str]] | None = None
        if self._live_listening and self._listening_mode is not None:
            passive_state = (self._listening_mode, list(self._live_wake_names))
            await self._stop_passive_listening()
        stt_config = self._cfg.stt.model_copy(
            update={
                "model": selected,
                "realtime_model_type": selected,
                "use_main_model_for_realtime": True,
            }
        )
        self._cfg = self._cfg.model_copy(update={"stt": stt_config})
        prepare = getattr(self._stt, "prepare", None)
        if callable(prepare):
            await cast(Callable[..., Awaitable[Any]], prepare)(
                self._dictation_config(mode="push_to_talk")
            )
        if passive_state is not None:
            await self._restore_passive_listening(passive_state)

    def _wake_match_phrases(self, names: list[str] | None = None) -> list[str]:
        return _normalise_wake_names(
            list(names if names is not None else self._configured_wake_names)
            + list(self._configured_wake_aliases)
        )

    async def set_post_speech_silence_duration(self, seconds: float) -> None:
        """Update phrase endpointing and restart an active passive listener.

        Push-to-talk reads the new value the next time its microphone session
        starts. Continuous and wake listeners are restarted immediately so the
        dashboard setting has an observable, deterministic effect.
        """

        value = float(seconds)
        if not 0.2 <= value <= 3.0:
            raise ValueError("end-of-speech pause must be between 0.2 and 3.0 seconds")
        if value == self._cfg.stt.post_speech_silence_duration:
            return

        passive_state: tuple[str, list[str]] | None = None
        if self._live_listening and self._listening_mode is not None:
            passive_state = (self._listening_mode, list(self._live_wake_names))
            await self._stop_passive_listening()

        stt_config = self._cfg.stt.model_copy(update={"post_speech_silence_duration": value})
        self._cfg = self._cfg.model_copy(update={"stt": stt_config})

        if passive_state is not None:
            await self._restore_passive_listening(passive_state)

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
        self._resume_listening_after_tts = None
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
        _log.info("SpeechController: %s listener consuming transcripts", self._listening_mode)
        try:
            async for transcript in self._stt.transcripts:
                if transcript.is_final:
                    _log.info(
                        "SpeechController: %s final dequeued: chars=%d",
                        self._listening_mode,
                        len(transcript.text),
                    )
                wake_match: tuple[str, str] | None = None
                if self._listening_mode == "wake":
                    wake_match = _extract_wake_command(transcript.text, self._live_wake_names)
                    if wake_match is None:
                        if transcript.is_final:
                            wake_announced = False
                            raw = transcript.text.strip()
                            if raw:
                                self._bus.publish(
                                    UserSpeechFinal(
                                        ts=_now(),
                                        text=raw,
                                        raw_text=raw,
                                        accepted=False,
                                        input_mode="wake",
                                        rejection_reason="wake_name_missing",
                                    )
                                )
                        continue
                    wake_name, command = wake_match
                    if not wake_announced:
                        self._bus.publish(WakeDetected(ts=_now(), name=wake_name))
                        wake_announced = True
                else:
                    command = transcript.text.strip()

                if transcript.is_final:
                    wake_announced = False
                    raw = transcript.text.strip()
                    if command:
                        accepted = True
                        rejection_reason = None
                        if self._listening_mode == "wake" and self._is_duplicate_wake(command):
                            accepted = False
                            rejection_reason = "duplicate"
                        _log.info(
                            "SpeechController: %s transcript %s: %r",
                            self._listening_mode,
                            "accepted" if accepted else "ignored duplicate",
                            command,
                        )
                        self._bus.publish(
                            UserSpeechFinal(
                                ts=_now(),
                                text=command,
                                raw_text=raw,
                                reason="normal",
                                accepted=accepted,
                                input_mode=(
                                    "wake" if self._listening_mode == "wake" else "continuous"
                                ),
                                rejection_reason=rejection_reason,
                            )
                        )
                    elif raw:
                        self._bus.publish(
                            UserSpeechFinal(
                                ts=_now(),
                                text=raw,
                                raw_text=raw,
                                accepted=False,
                                input_mode="wake",
                                rejection_reason="empty",
                            )
                        )
                else:
                    if command:
                        self._bus.publish(
                            TranscriptPreview(ts=_now(), text=command, is_final=False)
                        )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.warning("SpeechController._live_listener: %s", exc, exc_info=True)
        finally:
            _log.info("SpeechController: passive listener stopped")

    def _is_duplicate_wake(self, command: str) -> bool:
        normalised = " ".join(command.casefold().split())
        now = time.monotonic()
        previous = self._last_accepted_wake
        if (
            previous is not None
            and previous[0] == normalised
            and now - previous[1] <= _WAKE_DUPLICATE_WINDOW_SECONDS
        ):
            return True
        self._last_accepted_wake = (normalised, now)
        return False


def _normalise_wake_names(names: list[str]) -> list[str]:
    """Trim, de-duplicate, and prefer the longest prefix during matching."""

    unique: dict[str, str] = {}
    for raw in names:
        name = " ".join(str(raw).split()).strip(" ,.:;!?-")
        if name:
            unique.setdefault(name.casefold(), name)
    return sorted(unique.values(), key=len, reverse=True)


def _playback_timeout_seconds(text_or_stream: str | AsyncIterable[str]) -> float:
    """Bound a broken audio stream without truncating normal long replies."""

    if not isinstance(text_or_stream, str):
        return _TTS_MAX_TIMEOUT_SECONDS
    # A conservative 8 characters/second plus startup/driver padding.
    estimate = 12.0 + len(text_or_stream) / 8.0
    return min(_TTS_MAX_TIMEOUT_SECONDS, max(_TTS_MIN_TIMEOUT_SECONDS, estimate))


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
