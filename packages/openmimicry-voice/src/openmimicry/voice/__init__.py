"""openmimicry-voice: STTAdapter / TTSAdapter implementations + SpeechController.

Exports
-------

* :class:`STTAdapter`, :class:`TTSAdapter` — re-exported Protocols.
* :class:`MockSTTAdapter`, :class:`MockTTSAdapter` — canonical mocks.
* :class:`RealtimeSTTAdapter`, :class:`RealtimeTTSAdapter` — RealtimeSTT /
  RealtimeTTS-backed adapters (heavy deps are lazy-imported).
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
from .stt.realtimestt_adapter import (
    RealtimeSTTAdapter,
    RealtimeSTTSettings,
    RealtimeSTTUnavailable,
)
from .tts.realtimetts_adapter import (
    RealtimeTTSAdapter,
    RealtimeTTSSettings,
    RealtimeTTSUnavailable,
)

__all__ = [
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
    "TTSAdapter",
    "WakeController",
]

__version__ = "0.2.0a0"
