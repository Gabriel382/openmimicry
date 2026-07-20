"""Preloaded Faster-Whisper microphone service with finite utterance jobs."""

from __future__ import annotations

import argparse
import json
import queue
import sys
import tempfile
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Any

from .whisper_runtime import (
    WhisperRuntime,
    load_whisper_runtime,
    run_with_auto_cpu_fallback,
)


def _emit(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}), flush=True)


class Service:
    def __init__(self, args: argparse.Namespace) -> None:
        import numpy as np  # type: ignore[import-not-found]
        import sounddevice as sd  # type: ignore[import-not-found]

        self.np = np
        self.sd = sd
        self.requested_device = args.device
        self.runtime = load_whisper_runtime(
            args.model,
            requested_device=args.device,
            requested_compute_type=args.compute_type,
        )
        self.model = self.runtime.model
        self.device = self.runtime.device
        self.compute_type = self.runtime.compute_type
        self.model_name = args.model
        self.language = args.language
        self.sample_rate = args.sample_rate
        self.beam_size = args.beam_size
        self.prompt = args.prompt or None
        self.speech_threshold = args.speech_threshold
        self.silence_seconds = args.silence_seconds
        if self.runtime.fallback_reason:
            _emit(
                "runtime",
                message=self.runtime.fallback_reason,
                device=self.device,
                compute_type=self.compute_type,
            )
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self.audio: queue.Queue[Any] = queue.Queue(maxsize=400)
        self.stream: Any = None
        self.mode: str | None = None
        self.frames: list[Any] = []
        self.pre_roll: deque[Any] = deque(maxlen=max(1, int(0.4 / 0.03)))
        self.speaking = False
        self.last_voice_at = 0.0
        self.running = True
        threading.Thread(target=self._read_commands, daemon=True).start()

    def _read_commands(self) -> None:
        for line in sys.stdin:
            try:
                self.commands.put(json.loads(line))
            except json.JSONDecodeError:
                _emit("error", message="invalid command JSON")
        self.commands.put({"command": "shutdown", "id": 0})

    def _callback(self, indata: Any, _frames: int, _time: Any, status: Any) -> None:
        if status:
            print(str(status), file=sys.stderr, flush=True)
        try:
            self.audio.put_nowait(indata[:, 0].copy())
        except queue.Full:
            with self.audio.mutex:
                self.audio.queue.clear()

    def _start_stream(self, mode: str, silence_seconds: float) -> None:
        self._stop_stream()
        self.mode = mode
        self.silence_seconds = silence_seconds
        self.frames = []
        self.pre_roll.clear()
        self.speaking = False
        self.last_voice_at = 0.0
        with self.audio.mutex:
            self.audio.queue.clear()
        self.stream = self.sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=max(256, int(self.sample_rate * 0.03)),
            callback=self._callback,
        )
        self.stream.start()

    def _stop_stream(self) -> None:
        stream = self.stream
        self.stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        if self.speaking:
            _emit("vad", active=False)
        self.speaking = False

    def _handle_audio(self, block: Any) -> None:
        if self.mode == "push_to_talk" or self.mode == "dictation":
            self.frames.append(block)
            return
        if self.mode not in {"wake", "continuous"}:
            return
        rms = float(self.np.sqrt(self.np.mean(self.np.square(block))))
        now = time.monotonic()
        if not self.speaking:
            self.pre_roll.append(block)
            if rms >= self.speech_threshold:
                self.speaking = True
                self.frames = list(self.pre_roll)
                self.pre_roll.clear()
                self.last_voice_at = now
                _emit("vad", active=True)
            return
        self.frames.append(block)
        if rms >= self.speech_threshold:
            self.last_voice_at = now
        elif now - self.last_voice_at >= self.silence_seconds:
            frames = self.frames
            self.frames = []
            self.speaking = False
            _emit("vad", active=False)
            self._transcribe(frames)
            # Audio captured while the CPU/GPU was transcribing belongs to an
            # ambiguous interval. Drop it instead of replaying stale blocks as
            # another utterance or growing the queue forever.
            with self.audio.mutex:
                self.audio.queue.clear()

    def _write_wav(self, frames: list[Any]) -> Path:
        audio = self.np.concatenate(frames) if frames else self.np.zeros(0, dtype=self.np.float32)
        audio = self.np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767.0).astype(self.np.int16)
        with tempfile.NamedTemporaryFile(
            prefix="openmimicry-stt-", suffix=".wav", delete=False
        ) as handle:
            path = Path(handle.name)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return path

    def _transcribe(self, frames: list[Any]) -> None:
        if not frames:
            _emit("transcript", text="", is_final=True)
            return
        path = self._write_wav(frames)
        try:
            (text, confidence), runtime = run_with_auto_cpu_fallback(
                self.runtime,
                model_name=self.model_name,
                requested_device=self.requested_device,
                operation=lambda model: self._decode(model, path),
            )
            if runtime is not self.runtime:
                self._apply_runtime(runtime)
            _emit("transcript", text=text.strip(), is_final=True, confidence=confidence)
        finally:
            path.unlink(missing_ok=True)

    def _decode(self, model: Any, path: Path) -> tuple[str, float | None]:
        segments, info = model.transcribe(
            str(path),
            language=self.language,
            beam_size=self.beam_size,
            condition_on_previous_text=False,
            initial_prompt=self.prompt,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 250},
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return text, getattr(info, "language_probability", None)

    def _apply_runtime(self, runtime: WhisperRuntime) -> None:
        self.runtime = runtime
        self.model = runtime.model
        self.device = runtime.device
        self.compute_type = runtime.compute_type
        if runtime.fallback_reason:
            _emit(
                "runtime",
                message=runtime.fallback_reason,
                device=runtime.device,
                compute_type=runtime.compute_type,
            )

    def _ack(self, command: dict[str, Any], *, ok: bool = True, error: str | None = None) -> None:
        _emit("ack", id=int(command.get("id", 0)), ok=ok, error=error)

    def _handle_command(self, command: dict[str, Any]) -> None:
        name = command.get("command")
        try:
            if name == "start":
                self._start_stream(
                    str(command.get("mode") or "dictation"),
                    float(command.get("post_speech_silence_duration", self.silence_seconds)),
                )
                self._ack(command)
            elif name == "finish":
                self._stop_stream()
                while True:
                    try:
                        self.frames.append(self.audio.get_nowait())
                    except queue.Empty:
                        break
                frames = self.frames
                self.frames = []
                self.mode = None
                self._transcribe(frames)
                self._ack(command)
            elif name == "stop":
                self._stop_stream()
                self.frames = []
                self.mode = None
                self._ack(command)
            elif name == "shutdown":
                self._stop_stream()
                self._ack(command)
                self.running = False
            else:
                self._ack(command, ok=False, error=f"unknown command: {name}")
        except Exception as exc:
            self._ack(command, ok=False, error=f"{type(exc).__name__}: {exc}")

    def run(self) -> None:
        _emit(
            "ready",
            model=self.model_name,
            device=self.device,
            compute_type=self.compute_type,
            sample_rate=self.sample_rate,
            fallback_reason=self.runtime.fallback_reason,
        )
        while self.running:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            if command is not None:
                self._handle_command(command)
                continue
            if self.stream is not None:
                try:
                    block = self.audio.get(timeout=0.03)
                except queue.Empty:
                    continue
                self._handle_audio(block)
            else:
                time.sleep(0.02)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="medium.en")
    parser.add_argument("--language", default="en")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--compute-type", default="auto")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--speech-threshold", type=float, default=0.015)
    parser.add_argument("--silence-seconds", type=float, default=1.0)
    parser.add_argument("--prompt", default="")
    args = parser.parse_args()
    try:
        Service(args).run()
        return 0
    except Exception as exc:
        _emit("error", message=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
