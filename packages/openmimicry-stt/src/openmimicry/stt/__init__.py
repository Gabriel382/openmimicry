"""openmimicry-stt: sensor-layer facade over the STT half of openmimicry-voice.

This package exists so that the *sensor* layer of the architecture
(see ``docs/architecture/layers/sensors.md``) is also a physical,
independently installable package. The runtime implementation still
lives in ``openmimicry-voice``; this module re-exports the STT-relevant
adapters and the small controllers that sit above them.

Exports
-------

* :class:`STTAdapter` — re-exported Protocol from ``openmimicry.core``.
* :class:`MockSTTAdapter` — zero-dependency mock for unit tests.
* :class:`IsolatedFasterWhisperAdapter` — supported crash-contained runtime.
* :class:`RealtimeSTTAdapter` — legacy RealtimeSTT compatibility adapter.
* :class:`RealtimeSTTSettings`, :class:`RealtimeSTTUnavailable`.
* :class:`WakeController` — thin enable/disable wrapper for live-wake mode.
* :class:`SpeechController` — bridging controller that owns the
  single-TTS-task invariant. (Imported here for convenience even though
  it also touches the effector layer; full discussion in the cognition
  doc.)

Usage
-----

.. code-block:: python

    from openmimicry.stt import MockSTTAdapter, WakeController

The :data:`__version__` here tracks the facade. The underlying voice
package version is exposed as :data:`source_package_version`.
"""

from __future__ import annotations

from openmimicry.voice import (
    IsolatedFasterWhisperAdapter,
    IsolatedFasterWhisperSettings,
    IsolatedSTTUnavailable,
    MockSTTAdapter,
    RealtimeSTTAdapter,
    RealtimeSTTSettings,
    RealtimeSTTUnavailable,
    SpeechController,
    STTAdapter,
    WakeController,
)
from openmimicry.voice import __version__ as source_package_version

__all__ = [
    "IsolatedFasterWhisperAdapter",
    "IsolatedFasterWhisperSettings",
    "IsolatedSTTUnavailable",
    "MockSTTAdapter",
    "RealtimeSTTAdapter",
    "RealtimeSTTSettings",
    "RealtimeSTTUnavailable",
    "STTAdapter",
    "SpeechController",
    "WakeController",
    "source_package_version",
]

__version__ = "1.6.4"
