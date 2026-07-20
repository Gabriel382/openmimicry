"""Synthesize, validate, and play exactly one Piper utterance."""

from __future__ import annotations

import argparse
import json
import os
import sys
import wave
from pathlib import Path


def _emit(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}), flush=True)


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        rate = wav_file.getframerate()
        frames = wav_file.getnframes()
        if rate <= 0 or frames <= 0:
            raise RuntimeError("Piper produced an empty WAV")
        return frames / rate


def _play(path: Path) -> None:
    if os.name == "nt":
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return

    import numpy as np  # type: ignore[import-not-found]
    import sounddevice as sd  # type: ignore[import-not-found]

    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
    if sample_width != 2:
        raise RuntimeError(f"unsupported Piper sample width: {sample_width}")
    audio = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape((-1, channels))
    sd.play(audio, sample_rate, blocking=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--no-playback", action="store_true")
    args = parser.parse_args()
    text = sys.stdin.read().strip()
    if not text:
        _emit("error", message="empty text")
        return 2
    try:
        from piper import PiperVoice, SynthesisConfig  # type: ignore[import-not-found]

        model = Path(args.model).expanduser().resolve()
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        voice = PiperVoice.load(str(model))
        synthesis = SynthesisConfig(length_scale=1.0 / max(0.25, min(4.0, args.rate)))
        with wave.open(str(output), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=synthesis)
        duration_s = _duration(output)
        _emit("audio_ready", path=str(output), duration_s=duration_s)
        if not args.no_playback:
            _emit("playback_started", duration_s=duration_s)
            _play(output)
            _emit("playback_finished", duration_s=duration_s)
        return 0
    except Exception as exc:
        _emit("error", message=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
