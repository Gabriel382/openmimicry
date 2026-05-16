
from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from app.config import load_character, load_runtime
from app.stt_whisper_vad import WhisperVADAdapter, WhisperVADConfig
from app.tts_router import speak_with_fallback, stop_all_tts
from app.voice_models import VoiceSettings
from app.voice_state import VoiceMode, VoiceRuntimeState

@dataclass(slots=True)
class VoiceContext:
    wake_name: str
    wake_aliases: list[str]
    silence_padding_seconds: float
    max_record_time: int
    vad_aggressiveness: int
    min_command_duration_ms: int
    self_tts_cooldown_ms: int

class VoiceController:
    def __init__(self) -> None:
        runtime = load_runtime()
        char_name = runtime.get("ui", {}).get("active_character", "octomimic")
        character = load_character(char_name)
        voice_cfg = character.get("voice", {})
        rt_voice = runtime.get("voice", {})
        self.context = VoiceContext(
            wake_name=character.get("wake_name", "assistant").lower(),
            wake_aliases=[a.lower() for a in character.get("wake_aliases", [])],
            silence_padding_seconds=float(voice_cfg.get("silence_padding_seconds", 0.8)),
            max_record_time=int(voice_cfg.get("max_record_time", 10)),
            vad_aggressiveness=int(voice_cfg.get("vad_aggressiveness", 2)),
            min_command_duration_ms=int(voice_cfg.get("min_command_duration_ms", 350)),
            self_tts_cooldown_ms=int(rt_voice.get("self_tts_cooldown_ms", 1500)),
        )
        self.settings = VoiceSettings(
            live_wake_enabled=bool(rt_voice.get("live_wake_enabled_default", False)),
            push_to_talk_enabled=bool(rt_voice.get("push_to_talk_enabled_default", False)),
            agent_voice_enabled=bool(rt_voice.get("agent_voice_enabled_default", True)),
        )
        self.mode = VoiceMode.LIVE_WAKE if self.settings.live_wake_enabled else (VoiceMode.PUSH_TO_TALK if self.settings.push_to_talk_enabled else VoiceMode.OFF)
        self.runtime_state = VoiceRuntimeState.IDLE
        self.last_transcript = ""
        self.last_tts_started_at = 0.0
        self._lock = threading.Lock()
        self._live_thread: threading.Thread | None = None
        self._live_stop = threading.Event()
        self.stt = WhisperVADAdapter(
            WhisperVADConfig(
                aggressiveness=self.context.vad_aggressiveness,
                silence_padding=self.context.silence_padding_seconds,
                max_record_time=self.context.max_record_time,
            )
        )

    def status(self) -> dict:
        return {
            "mode": self.mode.value,
            "runtime_state": self.runtime_state.value,
            "live_wake_enabled": self.settings.live_wake_enabled,
            "push_to_talk_enabled": self.settings.push_to_talk_enabled,
            "agent_voice_enabled": self.settings.agent_voice_enabled,
            "last_transcript": self.last_transcript,
            "wake_name": self.context.wake_name,
        }

    def set_live_wake(self, enabled: bool) -> dict:
        self.settings.live_wake_enabled = enabled
        if enabled:
            self.settings.push_to_talk_enabled = False
            self.mode = VoiceMode.LIVE_WAKE
            self._ensure_live_loop()
        else:
            if self.mode == VoiceMode.LIVE_WAKE:
                self.mode = VoiceMode.OFF
            self._live_stop.set()
            self.runtime_state = VoiceRuntimeState.IDLE
        return self.status()

    def set_push_to_talk_mode(self, enabled: bool) -> dict:
        self.settings.push_to_talk_enabled = enabled
        if enabled:
            self.settings.live_wake_enabled = False
            self.mode = VoiceMode.PUSH_TO_TALK
            self._live_stop.set()
        else:
            if self.mode == VoiceMode.PUSH_TO_TALK:
                self.mode = VoiceMode.OFF
            self.runtime_state = VoiceRuntimeState.IDLE
        return self.status()

    def set_agent_voice(self, enabled: bool) -> dict:
        self.settings.agent_voice_enabled = enabled
        if not enabled:
            stop_all_tts()
            self.runtime_state = VoiceRuntimeState.INTERRUPTED
        return self.status()

    def interrupt_output(self) -> None:
        stop_all_tts()
        self.runtime_state = VoiceRuntimeState.INTERRUPTED

    def mark_speaking(self, text: str) -> None:
        self.last_tts_started_at = time.time()
        self.runtime_state = VoiceRuntimeState.SPEAKING
        if self.settings.agent_voice_enabled:
            speak_with_fallback(text)

    def ptt_start(self) -> dict:
        self.mode = VoiceMode.PUSH_TO_TALK
        self.settings.push_to_talk_enabled = True
        self.settings.live_wake_enabled = False
        self.runtime_state = VoiceRuntimeState.PTT_LISTENING
        stop_all_tts()
        return self.status()

    def ptt_stop_and_transcribe(self) -> dict:
        self.runtime_state = VoiceRuntimeState.TRANSCRIBING
        result = self.stt.listen_once()
        self.last_transcript = result.text
        self.runtime_state = VoiceRuntimeState.THINKING if result.text else VoiceRuntimeState.IDLE
        return {**self.status(), "transcript": result.text, "language": result.language, "contains_speech": result.contains_speech}

    def _ensure_live_loop(self) -> None:
        if self._live_thread and self._live_thread.is_alive():
            return
        self._live_stop.clear()
        self._live_thread = threading.Thread(target=self._live_loop, daemon=True)
        self._live_thread.start()

    def _self_tts_cooldown_active(self) -> bool:
        return (time.time() - self.last_tts_started_at) * 1000 < self.context.self_tts_cooldown_ms

    def _matches_wake(self, text: str) -> tuple[bool, str]:
        lowered = text.strip().lower()
        names = [self.context.wake_name, *self.context.wake_aliases]
        for name in names:
            if lowered.startswith(name + " "):
                return True, lowered[len(name):].strip()
            if lowered == name:
                return True, ""
        return False, ""

    def _live_loop(self) -> None:
        while not self._live_stop.is_set():
            if self.mode != VoiceMode.LIVE_WAKE:
                self.runtime_state = VoiceRuntimeState.IDLE
                time.sleep(0.15)
                continue
            self.runtime_state = VoiceRuntimeState.LIVE_WAITING_FOR_WAKE
            if self._self_tts_cooldown_active():
                time.sleep(0.15)
                continue
            result = self.stt.listen_once()
            if not result.contains_speech or result.duration_ms < self.context.min_command_duration_ms:
                continue
            self.last_transcript = result.text
            matched, command = self._matches_wake(result.text)
            if not matched:
                continue
            self.last_transcript = command
            self.runtime_state = VoiceRuntimeState.THINKING if command else VoiceRuntimeState.WAKE_FOLLOWUP_LISTENING
            time.sleep(0.1)

voice_controller = VoiceController()
