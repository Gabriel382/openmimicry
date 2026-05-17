# openmimicry-avatar

Avatar core for OpenMimicry: pack loader, director, orchestrator, and the canonical mock runtime.

## What's in the box

- **`MockAvatarRuntimeAdapter`** — recording fixture used by every other module's tests.
- **`AvatarDirector`** — state-machine that turns `RuntimeEvent` into `AvatarDirective` per the table in `docs/character_packs.md` §4.
- **`AvatarOrchestrator`** — owns the active `AvatarRuntimeAdapter`, subscribes to the bus, dispatches directives, schedules hold-and-return timers, and supports `swap_runtime(new)` with visual-state preservation (the current directive is re-emitted on the new runtime).
- **`load_pack(path)` / `validate_pack(path)`** — character-pack loader/validator with the fallback rules from §6: missing `_speaking` variants degrade to base frames; broken manifests refuse to load with structured errors.
- **`scripts/validate_pack.py`** — CLI wrapper that exits 1 on any error. Used by `make validate-packs` and CI.

Concrete runtimes (Sprite2D, Three.js, Live3D, Unity, External) plug in via the `openmimicry.contracts.avatar_runtime` entry point — M3 only ships the substrate.

## Install

```bash
pip install openmimicry-avatar
```

## Usage

```python
import asyncio
from openmimicry.core import EventBus
from openmimicry.core.schemas import UserSpeechStarted
from openmimicry.core.schemas.app import AvatarConfig
from openmimicry.avatar import (
    AvatarDirector,
    AvatarOrchestrator,
    MockAvatarRuntimeAdapter,
)
from datetime import datetime, timezone

async def main():
    bus = EventBus()
    runtime = MockAvatarRuntimeAdapter()
    director = AvatarDirector(config=AvatarConfig(pack="octomimic"))
    orch = AvatarOrchestrator(
        director=director, runtime=runtime, bus=bus, config=director.config,
    )
    await orch.start()

    # Publish an event; the orchestrator dispatches an AvatarDirective.
    bus.publish(UserSpeechStarted(ts=datetime.now(timezone.utc)))
    # Wait a beat for the consumer task to handle it.
    await asyncio.sleep(0.05)

    assert any(d.state == "listening" for d in runtime.directives_received)
    await orch.stop()

asyncio.run(main())
```

## Validating a pack

```bash
python scripts/validate_pack.py characters/octomimic/
python scripts/validate_pack.py --strict characters/    # warnings -> errors
```

## See also

- [`docs/contracts.md`](../../docs/contracts.md) §2.3, §2.4, §5 — frozen `AvatarDirective`, `CharacterPack`, and avatar Protocols.
- [`docs/modules/M3_avatar_core.md`](../../docs/modules/M3_avatar_core.md) — module brief.
- [`docs/character_packs.md`](../../docs/character_packs.md) — pack format, the state-machine table, fallback rules.
