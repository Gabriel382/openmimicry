"""Subprocess fake for isolated Piper adapter tests."""

from __future__ import annotations

import argparse
import json
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--output")
parser.add_argument("--rate")
parser.parse_args()
text = sys.stdin.read()
print(json.dumps({"event": "audio_ready", "duration_s": 0.01}), flush=True)
print(json.dumps({"event": "playback_started", "duration_s": 0.01}), flush=True)
if "hang" in text:
    time.sleep(300)
print(json.dumps({"event": "playback_finished", "duration_s": 0.01}), flush=True)
