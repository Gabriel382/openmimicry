
"""A tiny avatar director that converts plain text/backend status into avatar JSON."""

from __future__ import annotations

from avatar.response_schema import AvatarAction, BackendAvatarResponse


def build_avatar_response(user_text: str, model_text: str, backend_name: str) -> BackendAvatarResponse:
    """Create a lightweight structured response for the avatar runtime."""
    lowered = model_text.lower()
    has_text = bool(model_text.strip())

    if any(word in lowered for word in ["error", "failed", "exception", "problem"]):
        action = AvatarAction(
            state="error",
            emotion="worried",
            animation="error",
            next_state="idle",
            duration_ms=2200,
        )
    elif any(word in lowered for word in ["great", "nice", "perfect", "love", "awesome", "good"]):
        action = AvatarAction(
            state="happy",
            emotion="happy",
            animation="happy",
            next_state="idle",
            duration_ms=1800,
        )
    elif not has_text:
        action = AvatarAction(
            state="idle",
            emotion="neutral",
            animation="idle",
            next_state="idle",
            duration_ms=None,
        )
    else:
        action = AvatarAction(
            state="speaking",
            emotion="neutral",
            animation="idle",
            next_state="idle",
            duration_ms=None,
        )

    return BackendAvatarResponse(
        text=model_text,
        avatar=action,
        backend=backend_name,
    )
