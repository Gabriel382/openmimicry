"""Import the commercial-default local voice dependency set."""

import numpy  # noqa: F401
import sounddevice  # noqa: F401
from faster_whisper import WhisperModel  # noqa: F401
from openmimicry.voice import SystemCommandTTSAdapter  # noqa: F401

print("Faster-Whisper/system-command commercial voice imports OK")
