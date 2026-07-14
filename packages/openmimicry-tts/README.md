# openmimicry-tts

**Effector layer — TTS facade.** Part of the [OpenMimicry layered
architecture](../../docs/architecture/README.md).

This package lives in the **effector layer** of OpenMimicry. It
contains the text-to-speech half of the voice runtime: a mock for
testing and a RealtimeTTS-backed adapter for production.

## Why this package exists

OpenMimicry's architecture splits the system into five layers
(Foundation, Sensors, Cognition, Effectors, Surfaces). The effector
layer must be installable and developable in isolation — without
pulling in STT dependencies, an LLM, or the Tauri shell.

Today the concrete implementation lives in `openmimicry-voice`. This
package is a **thin facade** that re-exports the TTS half of that
implementation under a name that matches the architecture:
`openmimicry.tts`.

```python
# Before (still works):
from openmimicry.voice import MockTTSAdapter

# After (preferred — makes layer membership obvious):
from openmimicry.tts import MockTTSAdapter
```

Both imports return the same class. The facade does not duplicate
behaviour; it only renames it for the effector-layer consumer.

## What's inside

| Symbol | What it does |
|--------|--------------|
| `TTSAdapter` | The Protocol every TTS adapter must satisfy. Re-exported from `openmimicry.core.contracts.voice`. |
| `MockTTSAdapter` | Zero-dependency mock. Canonical fixture for the other layers' tests. |
| `RealtimeTTSAdapter` | RealtimeTTS-backed adapter. Supports Coqui/Piper/Azure/OpenAI/System engines via the underlying library. Heavy deps lazy-imported. |
| `RealtimeTTSSettings` | Pydantic settings for the RealtimeTTS adapter. |
| `RealtimeTTSUnavailable` | Raised when RealtimeTTS isn't installed. Used to fall back to mocks. |

## Install

```bash
# Mocks only (recommended for CI, dev workstations without audio out)
pip install openmimicry-tts

# With RealtimeTTS runtime (audio-device-bound)
pip install "openmimicry-tts[realtimetts]"
```

Heavy dependencies are lazy-imported inside the adapter, so even the
default install gives you the full type surface — you just can't open
audio output until you add the extra.

## Develop it in isolation

```bash
cd packages/openmimicry-tts

# The actual TTS adapter source still lives in openmimicry-voice, so
# the tests live there too. The facade is exercised by importing from it:
python -c "from openmimicry.tts import MockTTSAdapter; print(MockTTSAdapter)"

# Run the upstream tests against the facade name:
cd ../openmimicry-voice
python -m pytest tests/unit/voice/ -q
```

## Where does `SpeechController` live?

`SpeechController` coordinates *both* STT and TTS — when the user
interrupts mid-speech, when push-to-talk cancels an active utterance,
when a wake-word fires. Because it spans both layers, it lives in
the source-of-truth package (`openmimicry-voice`) and is also
re-exported from `openmimicry.stt` for convenience.

This package (`openmimicry-tts`) deliberately does **not** re-export
it — the speech controller belongs to the cognition layer, not the
effector layer.

## Future direction

When/if the source files physically move out of `openmimicry-voice`
(major-version migration), the facade simply changes from
`from openmimicry.voice import …` to native imports of the same names.
Consumer code does not change.

## Contracts

Every adapter in this package satisfies:

- [`openmimicry.core.contracts.voice.TTSAdapter`](../openmimicry-core/src/openmimicry/core/contracts/voice.py)

Contract tests live with the source package
(`packages/openmimicry-voice/tests/contract/`) and are
parametrised over every registered factory, so the facade is
automatically covered.

## License

MIT — same as the rest of the OpenMimicry project.
