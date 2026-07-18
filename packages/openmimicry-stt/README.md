# openmimicry-stt

**Sensor layer — STT facade.** Part of the [OpenMimicry layered
architecture](../../docs/architecture/README.md).

This package lives in the **sensor layer** of OpenMimicry. It contains
the speech-to-text half of the voice runtime: a mock for testing, the
crash-contained Faster-Whisper service used by v1.5, a legacy RealtimeSTT
adapter, and the `WakeController` that turns live-wake mode on and off.

## Why this package exists

OpenMimicry's architecture splits the system into five layers
(Foundation, Sensors, Cognition, Effectors, Surfaces). The sensor
layer must be installable and developable in isolation — without
pulling in TTS dependencies, an LLM, or the Tauri shell.

Today the concrete implementation lives in `openmimicry-voice`. This
package is a **thin facade** that re-exports the STT half of that
implementation under a name that matches the architecture:
`openmimicry.stt`.

```python
# Before (still works):
from openmimicry.voice import MockSTTAdapter

# After (preferred — makes layer membership obvious):
from openmimicry.stt import MockSTTAdapter
```

Both imports return the same class. The facade does not duplicate
behaviour; it only renames it for the sensor-layer consumer.

## What's inside

| Symbol | What it does |
|--------|--------------|
| `STTAdapter` | The Protocol every STT adapter must satisfy. Re-exported from `openmimicry.core.contracts.voice`. |
| `MockSTTAdapter` | Zero-dependency mock. Canonical fixture for the other layers' tests. |
| `IsolatedFasterWhisperAdapter` | Supported runtime. Preloads Faster-Whisper in a supervised child service and records finite utterances. |
| `IsolatedFasterWhisperSettings` | Worker lifecycle, device, compute, decoding, and VAD settings. |
| `IsolatedSTTUnavailable` | Actionable startup/runtime failure for the isolated service. |
| `RealtimeSTTAdapter` | Legacy RealtimeSTT compatibility adapter. Heavy deps lazy-imported. |
| `RealtimeSTTSettings` | Pydantic settings for the RealtimeSTT adapter. |
| `RealtimeSTTUnavailable` | Raised when RealtimeSTT isn't installed. Used to fall back to mocks. |
| `WakeController` | Enable/disable wrapper for the live-wake flow. |
| `SpeechController` | Cross-layer controller that owns the single-TTS-task invariant; re-exported here for convenience. |

## Install

```bash
# Mocks only (recommended for CI, dev workstations without a mic)
pip install openmimicry-stt

# Supported isolated runtime
pip install "openmimicry-stt[voice]"

# Legacy compatibility runtime
pip install "openmimicry-stt[realtimestt]"
```

Heavy dependencies are lazy-imported inside the adapter, so even the
default install gives you the full type surface — you just can't open
a microphone until you add the extra.

## Develop it in isolation

```bash
cd packages/openmimicry-stt

# The actual STT adapter source still lives in openmimicry-voice, so
# the tests live there too. The facade is exercised by importing from it:
python -c "from openmimicry.stt import MockSTTAdapter; print(MockSTTAdapter)"

# Run the upstream tests against the facade name:
cd ../openmimicry-voice
python -m pytest tests/unit/voice/ -q
```

## Future direction

When/if the source files physically move out of `openmimicry-voice`
(major-version migration), the facade simply changes from
`from openmimicry.voice import …` to native imports of the same names.
Consumer code does not change.

## Contracts

Every adapter in this package satisfies:

- [`openmimicry.core.contracts.voice.STTAdapter`](../openmimicry-core/src/openmimicry/core/contracts/voice.py)
- `WakeController`, `SpeechController` — see the same module.

Contract tests live with the source package
(`packages/openmimicry-voice/tests/contract/`) and are
parametrised over every registered factory, so the facade is
automatically covered.

## License

MIT — same as the rest of the OpenMimicry project.
