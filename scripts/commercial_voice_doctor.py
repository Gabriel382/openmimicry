"""Warm CPU STT and prove built-in OS speech can play more than once."""

from __future__ import annotations

import argparse
import asyncio
import json

import sounddevice
from faster_whisper import WhisperModel
from openmimicry.core import TTSConfig
from openmimicry.voice import SystemCommandTTSAdapter


async def _run(model_name: str, playback: bool) -> dict[str, object]:
    # CPU/int8 is the portable preflight lane. Runtime auto-selection may use
    # CUDA later, but a missing cublas DLL can never block startup again.
    await asyncio.to_thread(
        WhisperModel,
        model_name,
        device="cpu",
        compute_type="int8",
    )
    devices = await asyncio.to_thread(sounddevice.query_devices)
    adapter = SystemCommandTTSAdapter()
    config = TTSConfig(engine="system", voice="system-default")
    await adapter.prepare(config)
    if playback:
        await adapter.speak("OpenMimicry voice preflight, turn one.", config=config)
        await adapter.speak("OpenMimicry voice preflight, turn two.", config=config)
    await adapter.close()
    return {
        "version": "1.6.0",
        "passed": True,
        "stt_model": model_name,
        "stt_device": "cpu",
        "tts_adapter": "system-command",
        "playback_turns": 2 if playback else 0,
        "audio_devices": len(devices),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stt-model", default="medium.en")
    parser.add_argument("--playback", action="store_true")
    args = parser.parse_args()
    try:
        report = asyncio.run(_run(args.stt_model, args.playback))
    except Exception as exc:
        report = {
            "version": "1.6.0",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
