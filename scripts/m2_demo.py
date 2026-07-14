#!/usr/bin/env python3
"""M2 smoke demo -- wires SpeechController to mock STT/TTS, prints bus events.

Use cases (zero setup, no audio device touched):

* Default flow -- runs say(), then a PTT cycle, then live-wake, prints
  every RuntimeEvent the controller publishes:

      python scripts/m2_demo.py

* Just the say() path:

      python scripts/m2_demo.py --skip-ptt --skip-wake

* Drive a custom transcript through PTT:

      python scripts/m2_demo.py --ptt-text "what is the weather"

Exit code 0 on a clean run, 1 if any subscribed task crashes.

The demo intentionally uses the mock adapters so it can be run on any
machine -- no microphone, no speakers, no RealtimeSTT/TTS install. For
the real adapters, install `[realtimestt]` / `[realtimetts]` and write
your own wiring using openmimicry.voice.{RealtimeSTTAdapter,
RealtimeTTSAdapter} -- the SpeechController API is identical.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from collections.abc import Sequence

from openmimicry.core.bus import EventBus
from openmimicry.core.schemas.app import (
    STTConfigSection,
    STTWakeConfig,
    VoiceConfig,
    VoiceModesConfig,
)
from openmimicry.voice import MockSTTAdapter, MockTTSAdapter, SpeechController


async def _print_events(bus: EventBus, stop: asyncio.Event) -> None:
    """Subscribe to the bus and print every event with its kind + ts."""
    sub = bus.subscribe()
    async for event in sub:
        kind = getattr(event, "kind", "?")
        # Show a one-line summary of the salient fields.
        summary = []
        for attr in ("text", "full_text", "name", "where", "message"):
            value = getattr(event, attr, None)
            if value is not None:
                summary.append(f"{attr}={value!r}")
        line = f"  [{kind}]" + (" " + " ".join(summary) if summary else "")
        print(line)
        if stop.is_set():
            return


async def _run(args: argparse.Namespace) -> int:
    bus = EventBus()
    stt = MockSTTAdapter()
    tts = MockTTSAdapter(chunk_interval_s=0.02)

    cfg = VoiceConfig(
        stt=STTConfigSection(wake=STTWakeConfig(names=list(args.wake_names))),
        modes=VoiceModesConfig(barge_in_grace_ms=args.barge_in_grace_ms),
    )

    controller = SpeechController(stt=stt, tts=tts, bus=bus, config=cfg)
    await controller.start()

    stop = asyncio.Event()
    printer = asyncio.create_task(_print_events(bus, stop), name="m2_demo.printer")
    # Give the printer a chance to subscribe before events start flowing.
    await asyncio.sleep(0)

    print("--- say() ---", file=sys.stderr)
    await controller.say(args.text)
    # Wait until the TTS task finishes.
    if controller._current_tts_task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await controller._current_tts_task

    if not args.skip_ptt:
        print("--- ptt cycle ---", file=sys.stderr)
        await controller.ptt_down()
        await stt.push_transcript(args.ptt_text, is_final=True)
        await controller.ptt_up()

    if not args.skip_wake:
        print("--- live wake ---", file=sys.stderr)
        await controller.enable_live_listening()
        await stt.push_transcript("Mimi, are you there?", is_final=False)
        await asyncio.sleep(0.05)
        await stt.push_transcript("Mimi, hello.", is_final=True)
        await asyncio.sleep(0.05)
        await controller.disable_live_listening()

    if args.barge_in:
        print("--- barge-in scenario ---", file=sys.stderr)
        tts._chunk_interval_s = (
            0.2  # slow TTS so barge-in has time to fire  # type: ignore[attr-defined]
        )
        await controller.say("a very long sentence " * 5)
        await asyncio.sleep(0.05)
        await stt.trigger_speech_start()
        # Wait long enough for grace + recheck.
        await asyncio.sleep(0.5)
        await stt.trigger_speech_end()
        if controller._current_tts_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await controller._current_tts_task

    # Drain anything left.
    await asyncio.sleep(0.05)
    stop.set()
    await controller.stop()
    await bus.aclose()
    with contextlib.suppress(TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(printer, timeout=0.5)
    return 0


def _parse(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenMimicry M2 smoke demo")
    p.add_argument("--text", default="Hello from the voice mock.")
    p.add_argument(
        "--ptt-text",
        default="hello from the user",
        help="Final transcript pushed through STT during the PTT cycle.",
    )
    p.add_argument(
        "--wake-names",
        nargs="+",
        default=["Mimi", "Hey Mimi"],
        help="Wake names for the live-wake phase.",
    )
    p.add_argument("--barge-in", action="store_true", help="Exercise the barge-in path.")
    p.add_argument(
        "--barge-in-grace-ms",
        type=int,
        default=50,
        help="VoiceModesConfig.barge_in_grace_ms used by the demo.",
    )
    p.add_argument("--skip-ptt", action="store_true")
    p.add_argument("--skip-wake", action="store_true")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
