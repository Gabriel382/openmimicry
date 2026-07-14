# Layer: Foundation

The substrate every other layer is built on. Contains nothing that
talks to the network, the disk, or hardware — only types, an event
bus, and a runtime container.

## Packages

- [`openmimicry-core`](../../../packages/openmimicry-core/)
  - `openmimicry.core.contracts.*` — runtime-checkable Protocols.
    Anything below extends or consumes these.
  - `openmimicry.core.schemas.*` — frozen Pydantic v2 schemas
    (`AvatarDirective`, `RuntimeEvent`, `LLMChunk`, `VisionFrame`, …).
  - `openmimicry.core.EventBus` — bounded-queue async pub/sub.
  - `openmimicry.core.Runtime` — wires the bus + config + logging
    into one async-context-manager that every other module receives
    at startup.
  - `openmimicry.core.config.load` — YAML loader with env overlay,
    profile merge, and `schema_version` migrations.

## What lives here

- The 5 modality Protocols (LLM, STT, TTS, Avatar, Tasks).
- The Vision Protocol set (`VisionAdapter`, `LandmarkDetector`,
  `GestureClassifier`, `MovementClassifier`).
- The `RuntimeEvent` discriminated union — every variant the bus
  carries.
- `AppConfig` and its sub-configs (`LLMConfig`, `VoiceConfig`,
  `AvatarConfig`, `TasksConfig`, `VisionConfig`, …).
- The structured-logging tap that mirrors every event to logs.

## What doesn't live here

- Anything that opens a socket, a camera, or a microphone.
- Concrete adapter classes (those live in the implementation
  packages).
- HTTP / WebSocket transport (that's `apps/backend`).

## Develop it in isolation

```bash
cd packages/openmimicry-core
.venv\Scripts\python -m pytest tests/unit/core/ tests/contract/ -q
```

The core suite is hermetic — no optional dependencies, no network.
Adding a new event variant or schema field requires the change-control
procedure in [`../../contracts.md`](../../contracts.md) §11 (additive
amendments only within a minor version).

## Rule: do not import from siblings

`packages/openmimicry-core/src/openmimicry/core/` may not import from
`openmimicry.llm`, `openmimicry.voice`, `openmimicry.avatar`,
`openmimicry.tasks`, `openmimicry.vision`, or `openmimicry.stt` /
`openmimicry.tts`. `scripts/check_imports.py` enforces this in CI.

The reverse is fine: every other package imports liberally from
`openmimicry.core.*`.
