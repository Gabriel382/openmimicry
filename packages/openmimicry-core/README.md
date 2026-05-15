# openmimicry-core

The frozen contract surface and runtime services for OpenMimicry.

This package owns:

- The Protocols every adapter implements (`LLMAdapter`, `STTAdapter`, `TTSAdapter`, `TaskRuntimeAdapter`, `AvatarRuntimeAdapter`, `SpeechController`, `WakeController`, `AvatarDirector`, `AvatarOrchestrator`).
- The Pydantic schemas every module exchanges (`AppConfig`, `RuntimeEvent`, `AvatarDirective`, `LLMChunk`, `Transcript`, `TaskRequest`, …).
- The concrete `EventBus` (async fan-out, bounded queues, drop-oldest policy).
- The `RuntimeStore` (immutable snapshot of "what is true now").
- The `AppConfig` loader, profile overlay, env override, and hot-reload (`watchfiles`).
- Structured logging via `structlog` with a bus-tap subscriber.
- The `Runtime` context manager that wires the four together.

The shape lives in `openmimicry.core.contracts` and `openmimicry.core.schemas`. Both directories are **frozen**; do not change a signature, schema, or field name without going through `docs/contracts.md` §11.

## Quickstart

```python
import asyncio
from openmimicry.core import AppConfig
from openmimicry.core.runtime import Runtime

async def main():
    config = AppConfig()
    async with Runtime(config=config) as rt:
        # rt.bus is the event bus; rt.store is the live snapshot.
        ...

asyncio.run(main())
```

## Loading config

```python
from openmimicry.core.config import load
config = load("./config/app.yaml")  # respects OPENMIMICRY_CONFIG, OPENMIMICRY_PROFILE, OPENMIMICRY__SECTION__KEY
```

## Tests

This package's tests live at the repo root under `tests/unit/core/` and `tests/contract/`. Run them with `pytest -q` from the workspace root.

## See also

- `docs/contracts.md` — the immutable interface set.
- `docs/modules/M_phase0_contract_freeze.md` — Phase 0 brief.
- `docs/modules/M0_core.md` — M0 brief.
- `docs/configuration.md` — YAML schema and resolution order.
