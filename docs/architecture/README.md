# OpenMimicry — layered architecture

OpenMimicry's code is split into five layers. Each layer talks to the
next *only* through the frozen Protocols in `openmimicry-core` — never
through sibling-package imports. That rule, enforced by
`scripts/check_imports.py`, is what lets each layer be developed in
isolation with mocks at every boundary.

```
                       ┌────────────────────────────────────────────────┐
                       │ Surfaces                                       │
                       │ apps/backend   apps/desktop/frontend           │
                       │ apps/desktop/src-tauri   apps/unity-bridge     │
                       │ apps/external-echo                             │
                       └─────────────────────┬──────────────────────────┘
                                             │  Protocols
   ┌─────────────────────┐    ┌──────────────▼──────────────┐    ┌─────────────────────┐
   │ Sensors / Captors   │    │ Cognition                   │    │ Effectors / Actors  │
   │ openmimicry-stt     │    │ openmimicry-llm             │    │ openmimicry-tts     │
   │ openmimicry-vision  │◀──▶│ AvatarDirector (in avatar)  │◀──▶│ openmimicry-avatar  │
   │ (wake / PTT / live) │    │ detect_task_intent (tasks)  │    │ openmimicry-tasks   │
   └──────────┬──────────┘    └──────────────┬──────────────┘    └──────────┬──────────┘
              │                              │                              │
              └──────────────────────────────┼──────────────────────────────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │ Foundation                  │
                              │ openmimicry-core            │
                              │ ─ Protocols + Schemas        │
                              │ ─ EventBus / Runtime         │
                              │ ─ AppConfig loader           │
                              └─────────────────────────────┘
```

## The layers

| Layer | What it does | Read |
|-------|--------------|------|
| **Foundation** | Frozen Protocols, schemas, EventBus, Runtime, AppConfig. Everything else builds on this. | [`foundation.md`](layers/foundation.md) |
| **Sensors / Captors** | Pure inputs — anything that observes the user or the world. | [`sensors.md`](layers/sensors.md) |
| **Cognition** | Pure decision-making — LLM calls, director state machine, intent classification. | [`cognition.md`](layers/cognition.md) |
| **Effectors / Actors** | Pure outputs — anything that acts on the user or the world. | [`effectors.md`](layers/effectors.md) |
| **Surfaces** | The presentation + assembly. UI, transport, the one file that wires concrete adapters. | [`surfaces.md`](layers/surfaces.md) |

## How to work on one layer at a time

Every layer is independently installable, testable, and replaceable.
The detailed guide is in [`working_independently.md`](working_independently.md);
the short version is:

```bash
# Work on just the sensor layer (e.g. add a new gesture classifier):
cd packages/openmimicry-vision
.venv\Scripts\python -m pytest tests/unit/vision/ -q
# Every other package is mocked at the contract boundary — no LLM key
# needed, no microphone, no Tauri shell, no FastAPI server.
```

## Rules every layer obeys

1. **Contracts in, Protocols out.** A layer's only legitimate import
   from outside its package is `openmimicry.core.*`. Sibling-package
   imports are forbidden (CI enforces it).
2. **Mocks come first.** Every layer ships a `Mock<Whatever>` that
   satisfies its Protocol with zero optional dependencies. That mock
   is the canonical test fixture for the *other* layers.
3. **Real implementations are optional installs.** Heavy deps
   (LiteLLM, RealtimeSTT, MediaPipe, etc.) live behind `[extras]` and
   are lazy-imported. Default `pip install` is mocks-only.
4. **The assembly point is named.** Exactly one file in the
   repository is allowed to import concrete adapter classes:
   `apps/backend/src/openmimicry_backend/wiring.py`. That's the
   surface where the layers are physically connected.

## Mapping between conceptual layers and installable packages

| Conceptual layer | Installable package(s) | Notes |
|------------------|------------------------|-------|
| Foundation | `openmimicry-core` | Frozen contracts. Touch only via the change-control procedure in `docs/contracts.md` §11. |
| Sensors | `openmimicry-stt`, `openmimicry-vision` | `openmimicry-stt` is a facade today over the STT half of `openmimicry-voice`; future major version splits the source. |
| Cognition | `openmimicry-llm` | Plus `AvatarDirector` (lives inside `openmimicry-avatar`) and `detect_task_intent` (inside `openmimicry-tasks`). Cognition spans multiple packages by design — state machines belong with their state. |
| Effectors | `openmimicry-tts`, `openmimicry-avatar`, `openmimicry-tasks` | `openmimicry-tts` is a facade today over the TTS half of `openmimicry-voice`. |
| Surfaces | `apps/backend`, `apps/desktop/frontend`, `apps/desktop/src-tauri`, `apps/unity-bridge`, `apps/external-echo` | Each is a deployable; only `wiring.py` imports concrete adapter classes. |

(Reminder: `openmimicry-voice` still exists — it's the source-of-truth
package today and stt/tts are thin wrappers over it. You can import
from any of the three names. The wrappers exist so the layered
mental model is also a physical one.)
