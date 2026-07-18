"""Subprocess fake for isolated Faster-Whisper adapter tests."""

from __future__ import annotations

import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.parse_known_args()
print(
    json.dumps(
        {
            "event": "ready",
            "model": "fake-medium.en",
            "device": "cpu",
            "compute_type": "int8",
        }
    ),
    flush=True,
)
turn = 0
for line in sys.stdin:
    message = json.loads(line)
    command = message["command"]
    if command == "finish":
        turn += 1
        print(
            json.dumps({"event": "transcript", "text": f"voice turn {turn}", "is_final": True}),
            flush=True,
        )
    print(json.dumps({"event": "ack", "id": message["id"], "ok": True}), flush=True)
    if command == "shutdown":
        break
