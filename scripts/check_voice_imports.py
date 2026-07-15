"""Import the optional Windows voice engines without PowerShell quoting.

This script intentionally does not instantiate either engine.  The Windows
launcher executes it as a file so Windows PowerShell never has to serialize a
multiline ``python -c`` argument containing quotes.
"""

from RealtimeSTT import AudioToTextRecorder  # noqa: F401
from RealtimeTTS import SystemEngine, TextToAudioStream  # noqa: F401

print("RealtimeSTT/RealtimeTTS imports OK")
