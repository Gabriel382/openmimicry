"""openmimicry-tts: effector-layer facade over the TTS half of openmimicry-voice.

This package exists so that the *effector* layer of the architecture
(see ``docs/architecture/layers/effectors.md``) is also a physical,
independently installable package. The runtime implementation still
lives in ``openmimicry-voice``; this module re-exports the TTS-relevant
adapters.

Exports
-------

* :class:`TTSAdapter` — re-exported Protocol from ``openmimicry.core``.
* :class:`MockTTSAdapter` — zero-dependency mock for unit tests.
* :class:`RealtimeTTSAdapter` — RealtimeTTS-backed adapter
  (lazy-imports heavy deps).
* :class:`RealtimeTTSSettings`, :class:`RealtimeTTSUnavailable`.

Usage
-----

.. code-block:: python

    from openmimicry.tts import MockTTSAdapter

The :data:`__version__` here tracks the facade. The underlying voice
package version is exposed as :data:`source_package_version`.
"""

from __future__ import annotations

from openmimicry.voice import (
    MockTTSAdapter,
    RealtimeTTSAdapter,
    RealtimeTTSSettings,
    RealtimeTTSUnavailable,
    TTSAdapter,
)
from openmimicry.voice import __version__ as source_package_version

__all__ = [
    "MockTTSAdapter",
    "RealtimeTTSAdapter",
    "RealtimeTTSSettings",
    "RealtimeTTSUnavailable",
    "TTSAdapter",
    "source_package_version",
]

__version__ = "1.0.0"
