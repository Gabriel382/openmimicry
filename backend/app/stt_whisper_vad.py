
from __future__ import annotations
import collections
import queue
import time
from dataclasses import dataclass
import numpy as np
import sounddevice as sd
import webrtcvad
import whisper
from app.stt_base import BaseSTTAdapter, STTResult

@dataclass(slots=True)
class WhisperVADConfig:
    model_name: str = "small"
    samplerate: int = 16000
    frame_duration_ms: int = 30
    padding_duration_ms: int = 300
    aggressiveness: int = 2
    silence_padding: float = 0.8
    max_record_time: int = 10
    task: str = "translate"

class WhisperVADAdapter(BaseSTTAdapter):
    name = "whisper_vad"

    def __init__(self, config: WhisperVADConfig | None = None) -> None:
        self.config = config or WhisperVADConfig()
        self.model = whisper.load_model(self.config.model_name)

    def available(self) -> bool:
        return True

    def listen_once(self) -> STTResult:
        samplerate = self.config.samplerate
        frame_duration_ms = self.config.frame_duration_ms
        frame_size = int(samplerate * frame_duration_ms / 1000)
        num_padding_frames = int(self.config.padding_duration_ms / frame_duration_ms)
        vad = webrtcvad.Vad(self.config.aggressiveness)
        audio_queue: queue.Queue[bytes] = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(bytes(indata))

        ring_buffer = collections.deque(maxlen=num_padding_frames)
        triggered = False
        voiced_frames: list[bytes] = []
        start_time = time.time()
        silence_start_time = None

        with sd.RawInputStream(samplerate=samplerate, blocksize=frame_size, dtype="int16", channels=1, callback=audio_callback):
            while True:
                if time.time() - start_time > self.config.max_record_time:
                    break
                frame = audio_queue.get()
                is_speech = vad.is_speech(frame, samplerate)
                if not triggered:
                    ring_buffer.append((frame, is_speech))
                    num_voiced = len([1 for _, speech in ring_buffer if speech])
                    if ring_buffer.maxlen and num_voiced > 0.9 * ring_buffer.maxlen:
                        triggered = True
                        voiced_frames.extend([f for f, _ in ring_buffer])
                        ring_buffer.clear()
                else:
                    voiced_frames.append(frame)
                    ring_buffer.append((frame, is_speech))
                    num_unvoiced = len([1 for _, speech in ring_buffer if not speech])
                    if ring_buffer.maxlen and num_unvoiced > 0.9 * ring_buffer.maxlen:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > self.config.silence_padding:
                            break
                    else:
                        silence_start_time = None

        audio_bytes = b"".join(voiced_frames)
        if not audio_bytes:
            return STTResult(text="", language="unknown", duration_ms=0, contains_speech=False)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio_np) == 0:
            return STTResult(text="", language="unknown", duration_ms=0, contains_speech=False)

        result = self.model.transcribe(audio_np, fp16=False, task=self.config.task)
        text = result.get("text", "").strip()
        language = result.get("language", "unknown")
        duration_ms = int(len(audio_np) / samplerate * 1000)
        return STTResult(text=text, language=language, duration_ms=duration_ms, contains_speech=bool(text))

    def close(self) -> None:
        return
