
from __future__ import annotations
from enum import Enum

class VoiceMode(str, Enum):
    OFF = "off"
    LIVE_WAKE = "live_wake"
    PUSH_TO_TALK = "push_to_talk"

class VoiceRuntimeState(str, Enum):
    IDLE = "idle"
    LIVE_WAITING_FOR_WAKE = "live_waiting_for_wake"
    PTT_LISTENING = "ptt_listening"
    WAKE_FOLLOWUP_LISTENING = "wake_followup_listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
