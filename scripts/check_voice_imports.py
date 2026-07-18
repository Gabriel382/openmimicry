"""Import the v1.5 isolated voice dependencies without PowerShell quoting.

This script intentionally does not instantiate either engine. The Windows
launcher executes it as a file so Windows PowerShell never has to serialize a
multiline ``python -c`` argument containing quotes.
"""

import numpy  # noqa: F401
import sounddevice  # noqa: F401
from faster_whisper import WhisperModel  # noqa: F401
from piper import PiperVoice  # noqa: F401

print("Faster-Whisper/Piper isolated voice imports OK")
