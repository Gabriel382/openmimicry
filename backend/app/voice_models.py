
from __future__ import annotations
from pydantic import BaseModel

class VoiceSettings(BaseModel):
    live_wake_enabled: bool = False
    push_to_talk_enabled: bool = False
    agent_voice_enabled: bool = True

class VoiceToggleRequest(BaseModel):
    enabled: bool

class VoicePTTRequest(BaseModel):
    action: str
