"""Exercise the real v1.5 voice path before enabling it in the application."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from openmimicry.voice.workers.whisper_runtime import (
    load_whisper_runtime,
    run_with_auto_cpu_fallback,
)


def _validate_wav(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if frames <= 0 or rate <= 0:
            raise RuntimeError(f"invalid empty WAV: {path}")
        return frames / rate


def _run_piper(*, model: Path, output: Path, text: str, playback: bool) -> tuple[float, float]:
    command = [
        sys.executable,
        "-m",
        "openmimicry.voice.workers.piper_job",
        "--model",
        str(model),
        "--output",
        str(output),
    ]
    if not playback:
        command.append("--no-playback")
    started = time.monotonic()
    completed = subprocess.run(
        command,
        input=text,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip())
    return time.monotonic() - started, _validate_wav(output)


def _audio_devices() -> tuple[str, str]:
    import sounddevice as sd

    devices = sd.query_devices()
    inputs = [device["name"] for device in devices if device["max_input_channels"] > 0]
    outputs = [device["name"] for device in devices if device["max_output_channels"] > 0]
    if not inputs:
        raise RuntimeError("no microphone input device is available")
    if not outputs:
        raise RuntimeError("no speaker output device is available")
    return str(inputs[0]), str(outputs[0])


def _transcribe(path: Path, *, model_name: str) -> tuple[str, float, dict[str, object]]:
    started = time.monotonic()
    runtime = load_whisper_runtime(
        model_name,
        requested_device="auto",
        requested_compute_type="auto",
    )
    text, runtime = run_with_auto_cpu_fallback(
        runtime,
        model_name=model_name,
        requested_device="auto",
        operation=lambda model: _decode_sample(model, path),
    )
    if not text:
        raise RuntimeError("Faster-Whisper returned an empty preflight transcript")
    details: dict[str, object] = {
        "device": runtime.device,
        "compute_type": runtime.compute_type,
    }
    if runtime.fallback_reason:
        details["fallback_reason"] = runtime.fallback_reason
    return text, time.monotonic() - started, details


def _decode_sample(model: object, path: Path) -> str:
    segments, _info = model.transcribe(  # type: ignore[attr-defined]
        str(path),
        language="en",
        beam_size=5,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", default="en_US-lessac-medium")
    parser.add_argument("--voice-dir", default="~/.openmimicry/voices")
    parser.add_argument("--stt-model", default="medium.en")
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--playback", action="store_true")
    args = parser.parse_args()

    voice_dir = Path(args.voice_dir).expanduser().resolve()
    model = voice_dir / f"{args.voice}.onnx"
    report: dict[str, object] = {
        "version": "1.6.0",
        "passed": False,
        "voice": args.voice,
        "stt_model": args.stt_model,
        "tts_turns": [],
    }
    try:
        if not model.is_file():
            raise RuntimeError(f"Piper model is missing: {model}")
        model_config = Path(f"{model}.json")
        if not model_config.is_file():
            raise RuntimeError(f"Piper model configuration is missing: {model_config}")
        microphone, speaker = _audio_devices()
        report["microphone"] = microphone
        report["speaker"] = speaker
        with tempfile.TemporaryDirectory(prefix="openmimicry-doctor-") as temp_dir:
            first_wav: Path | None = None
            for turn in range(1, max(2, args.turns) + 1):
                output = Path(temp_dir) / f"turn-{turn:02d}.wav"
                elapsed, duration = _run_piper(
                    model=model,
                    output=output,
                    text=f"Open Mimicry voice preflight turn {turn}.",
                    playback=args.playback and turn == max(2, args.turns),
                )
                if first_wav is None:
                    first_wav = output
                report["tts_turns"].append(  # type: ignore[union-attr]
                    {"turn": turn, "elapsed_s": round(elapsed, 3), "duration_s": round(duration, 3)}
                )
            assert first_wav is not None
            transcript, elapsed, runtime = _transcribe(first_wav, model_name=args.stt_model)
            report["stt"] = {
                "transcript": transcript,
                "elapsed_s": round(elapsed, 3),
                **runtime,
            }
        report["passed"] = True
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(report, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
