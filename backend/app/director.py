
from __future__ import annotations
from app.schemas import AvatarDirective

def decide_avatar(text: str) -> AvatarDirective:
    lowered = text.lower()
    if any(word in lowered for word in ["error", "failed", "problem", "wrong"]):
        return AvatarDirective(emotion="error", animation="error_speaking", speaking=True, next_state="idle")
    if any(word in lowered for word in ["hello", "great", "good", "nice", "perfect", "love", "awesome"]):
        return AvatarDirective(emotion="happy", animation="happy_speaking", speaking=True, next_state="idle")
    return AvatarDirective(emotion="idle", animation="idle_speaking", speaking=True, next_state="idle")
