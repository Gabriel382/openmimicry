"""openmimicry-voice: STTAdapter / TTSAdapter implementations + SpeechController.

Exports
-------

* :class:`STTAdapter`, :class:`TTSAdapter` — re-exported Protocols.
* :class:`MockSTTAdapter`, :class:`MockTTSAdapter` — canonical mocks.
* :class:`IsolatedFasterWhisperAdapter` — supervised, preloaded STT service.
* :class:`IsolatedPiperTTSAdapter` — disposable per-utterance TTS jobs.
* :class:`RealtimeSTTAdapter`, :class:`RealtimeTTSAdapter` — legacy
  compatibility adapters (heavy deps are lazy-imported).
* :class:`SpeechController` — owns the single active TTS task and the
  barge-in policy.
* :class:`WakeController` — thin enable/disable wrapper.

See ``docs/contracts.md`` §4 for the immutable interface and
``docs/modules/M2_voice.md`` for the module brief.
"""

from __future__ import annotations

from openmimicry.core.contracts import STTAdapter, TTSAdapter

from .controllers.speech import SpeechController
from .controllers.wake import WakeController
from .mocks import MockSTTAdapter, MockTTSAdapter
from .stt.isolated_faster_whisper import (
    IsolatedFasterWhisperAdapter,
    IsolatedFasterWhisperSettings,
    IsolatedSTTUnavailable,
)
from .stt.realtimestt_adapter import (
    RealtimeSTTAdapter,
    RealtimeSTTSettings,
    RealtimeSTTUnavailable,
)
from .tts.chatterbox import ChatterboxSettings, ChatterboxTTSAdapter
from .tts.elevenlabs import ElevenLabsSettings, ElevenLabsTTSAdapter
from .tts.isolated_piper import (
    IsolatedPiperSettings,
    IsolatedPiperTTSAdapter,
    IsolatedTTSUnavailable,
)
from .tts.realtimetts_adapter import (
    RealtimeTTSAdapter,
    RealtimeTTSSettings,
    RealtimeTTSUnavailable,
)
from .tts.system_command import SystemCommandTTSAdapter, SystemTTSUnavailable

__all__ = [
    "ChatterboxSettings",
    "ChatterboxTTSAdapter",
    "ElevenLabsSettings",
    "ElevenLabsTTSAdapter",
    "IsolatedFasterWhisperAdapter",
    "IsolatedFasterWhisperSettings",
    "IsolatedPiperSettings",
    "IsolatedPiperTTSAdapter",
    "IsolatedSTTUnavailable",
    "IsolatedTTSUnavailable",
    "MockSTTAdapter",
    "MockTTSAdapter",
    "RealtimeSTTAdapter",
    "RealtimeSTTSettings",
    "RealtimeSTTUnavailable",
    "RealtimeTTSAdapter",
    "RealtimeTTSSettings",
    "RealtimeTTSUnavailable",
    "STTAdapter",
    "SpeechController",
    "SystemCommandTTSAdapter",
    "SystemTTSUnavailable",
    "TTSAdapter",
    "WakeController",
]

__version__ = "1.8.5"
