"""Map backend/runtime events to avatar states."""

from __future__ import annotations

from .state_model import AvatarState


def state_from_event(event_type: str) -> AvatarState:
    """Map a runtime event type to one of the avatar states.

    This keeps the first version intentionally simple.
    """
    lowered = event_type.strip().lower()

    if "listening" in lowered:
        return AvatarState.LISTENING
    if "thinking" in lowered or "request.started" in lowered:
        return AvatarState.THINKING
    if "speaking" in lowered or "response.delta" in lowered or "response.completed" in lowered:
        return AvatarState.SPEAKING
    if "happy" in lowered or "success" in lowered:
        return AvatarState.HAPPY
    if "error" in lowered or "failed" in lowered:
        return AvatarState.ERROR
    return AvatarState.IDLE
