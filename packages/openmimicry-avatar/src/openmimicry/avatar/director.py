"""``AvatarDirector`` — state machine that turns ``RuntimeEvent`` into ``AvatarDirective``.

Implements the table in ``docs/character_packs.md`` §4 cell-by-cell:

| state \\ Event | UserSpeechStarted | LLMStarted | TTSStarted | TTSChunkSpoken | TTSFinished | Error | TaskCompleted |
| idle           | listening         | thinking   | speaking*  | —              | —           | error | happy         |
| listening      | —                 | thinking   | speaking*  | —              | —           | error | happy         |
| thinking       | listening         | —          | speaking*  | —              | idle        | error | happy         |
| speaking       | listening         | —          | —          | speaking*      | idle        | error | happy         |
| happy          | listening         | thinking   | speaking*  | —              | —           | error | —             |
| error          | listening         | thinking   | speaking*  | —              | —           | —     | —             |

``speaking*`` means the directive sets ``speaking=True``.

Hold-and-return (``happy``, ``error``) is expressed on the directive via
``next_state`` + ``duration_ms``; the orchestrator owns the timer and the
re-emit. Any newer event that produces a directive supersedes the pending
return automatically because the director just produces directives — it
doesn't maintain timers itself.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openmimicry.core.schemas import (
    AvatarDirective,
    Emotion,
    ErrorEvent,
    LLMReplyComplete,
    LLMStarted,
    LLMTokenStreamed,
    State,
    TaskCompleted,
    TranscriptPreview,
    TTSChunkSpoken,
    TTSFinished,
    TTSInterrupted,
    TTSStarted,
    UserSpeechFinal,
    UserSpeechStarted,
    UserTextSubmitted,
    WakeDetected,
)
from openmimicry.core.schemas.app import AvatarConfig

if TYPE_CHECKING:
    from openmimicry.core.schemas import RuntimeEvent

__all__ = ["AvatarDirector"]


_log = logging.getLogger(__name__)


# Per-state emotion mapping per character_packs.md §4: "happy" state ->
# happy emotion; "error" state -> worried emotion; everything else neutral.
_DEFAULT_EMOTION_FOR_STATE: dict[State, Emotion] = {
    "idle": "neutral",
    "listening": "neutral",
    "thinking": "focused",
    "speaking": "neutral",
    "happy": "happy",
    "error": "worried",
}


class AvatarDirector:
    """Concrete director — stateful only in the sense of "what state am I in now"."""

    def __init__(self, config: AvatarConfig | None = None) -> None:
        self._cfg = config or AvatarConfig()
        self._state: State = self._cfg.default_state
        self._emotion: Emotion = self._cfg.default_emotion

    # ------------------------------------------------------------- properties

    @property
    def state(self) -> State:
        return self._state

    @property
    def emotion(self) -> Emotion:
        return self._emotion

    @property
    def config(self) -> AvatarConfig:
        return self._cfg

    # ----------------------------------------------------------------- API

    def on_event(self, event: "RuntimeEvent") -> AvatarDirective | None:
        """Map ``event`` to the next ``AvatarDirective``, or ``None`` for a no-op.

        Returning ``None`` is significant: it means *do not re-render*. The
        orchestrator simply doesn't dispatch.
        """
        next_state, speaking_override = self._next_state(event)
        if next_state is None:
            return None

        # Determine `speaking` flag.
        speaking = speaking_override
        if next_state == "speaking":
            speaking = True

        emotion = _DEFAULT_EMOTION_FOR_STATE.get(next_state, "neutral")

        # ``text`` propagation: surface the user/assistant text when we have it
        # so downstream renderers can show a speech-bubble preview.
        text = _event_text(event)

        # Hold-and-return for happy / error states. The orchestrator
        # consumes ``next_state`` + ``duration_ms`` to schedule the return.
        return_state: State | None = None
        hold_ms: int | None = None
        if next_state == "happy":
            return_state = "idle"
            hold_ms = self._cfg.celebration_ms
        elif next_state == "error":
            return_state = "idle"
            hold_ms = self._cfg.error_ms

        directive = AvatarDirective(
            state=next_state,
            emotion=emotion,
            speaking=speaking,
            text=text,
            next_state=return_state,
            duration_ms=hold_ms,
        )

        # Commit the state transition AFTER building the directive so
        # observers can read the prior state if they want.
        self._state = next_state
        self._emotion = emotion
        return directive

    def apply_return_to(self, return_to: State) -> AvatarDirective:
        """Synthesise a directive that returns the avatar to ``return_to``.

        Used by the orchestrator when a hold-and-return timer fires. We
        emit a directive instead of mutating state directly so every
        consumer sees the change uniformly.
        """
        emotion = _DEFAULT_EMOTION_FOR_STATE.get(return_to, "neutral")
        directive = AvatarDirective(state=return_to, emotion=emotion, speaking=False)
        self._state = return_to
        self._emotion = emotion
        return directive

    # ---------------------------------------------------------- state machine

    def _next_state(self, event: "RuntimeEvent") -> tuple[State | None, bool]:
        """Return ``(next_state_or_None, speaking_flag)`` for ``event``."""
        s = self._state

        # The mapping table from character_packs.md §4. A cell of "—" means
        # we return (None, False) -> no directive emitted.
        if isinstance(event, UserSpeechStarted):
            return ("listening", False) if s != "listening" else (None, False)

        if isinstance(event, LLMStarted):
            # idle/listening/happy/error -> thinking; others -> no-op.
            if s in ("idle", "listening", "happy", "error"):
                return "thinking", False
            return None, False

        if isinstance(event, TTSStarted):
            # idle/listening/thinking/happy/error -> speaking (speaking=True)
            # speaking -> no-op
            if s == "speaking":
                return None, False
            return "speaking", True

        if isinstance(event, TTSChunkSpoken):
            # Only meaningful while in speaking state: heartbeat with speaking=True.
            if s == "speaking":
                return "speaking", True
            return None, False

        if isinstance(event, (TTSFinished, TTSInterrupted)):
            # thinking/speaking -> idle; others -> no-op.
            if s in ("thinking", "speaking"):
                return "idle", False
            return None, False

        if isinstance(event, ErrorEvent):
            # error state itself: no-op (already in error).
            if s == "error":
                return None, False
            return "error", False

        if isinstance(event, TaskCompleted):
            # happy/error: no-op (don't override existing transient state)
            if s in ("happy", "error"):
                return None, False
            return "happy", False

        # ---- Soft events the table doesn't list, but we still react to. ----

        if isinstance(event, UserTextSubmitted):
            # Typing the same as starting LLM intent: transition to thinking
            # so the avatar shows it's working on a response.
            if s in ("idle", "listening", "happy", "error"):
                return "thinking", False
            return None, False

        if isinstance(event, UserSpeechFinal):
            # Speech ended without a new TTS yet: park at "thinking" so the
            # user sees the avatar is processing.
            if s == "listening":
                return "thinking", False
            return None, False

        if isinstance(event, WakeDetected):
            # Wake word: same effect as user starting speech.
            return ("listening", False) if s != "listening" else (None, False)

        if isinstance(event, LLMTokenStreamed):
            # Per-token heartbeat while thinking; if TTS has not started yet,
            # we don't re-emit. Once TTS starts, TTSStarted handles the
            # transition.
            return None, False

        if isinstance(event, LLMReplyComplete):
            # If TTS never started (text-only path), bounce back to idle so
            # the avatar doesn't stay "thinking" forever.
            if s == "thinking":
                return "idle", False
            return None, False

        if isinstance(event, TranscriptPreview):
            # No state transition on partials -- the speech-bubble preview
            # is the frontend's concern.
            return None, False

        # ConfigUpdated, TaskSubmitted, TaskUpdatedEvent: no avatar-side reaction.
        return None, False


def _event_text(event: "RuntimeEvent") -> str | None:
    """Extract a salient text field from an event for the speech bubble."""
    for attr in ("text", "full_text", "delta"):
        value = getattr(event, attr, None)
        if isinstance(value, str) and value:
            return value
    return None
