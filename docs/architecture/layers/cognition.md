# Layer: Cognition

Anything that **decides**. Consumes events from the sensor layer,
produces directives the effector layer acts on. Cognition is the
layer where "what should the avatar do next?" gets answered.

Cognition is the only layer that doesn't map 1-to-1 with a single
package — its components live wherever their state lives, so they
import the bare minimum from foundation only.

## Components

| Component | Lives in | What it decides |
|-----------|----------|-----------------|
| **LLM adapter / router** | [`openmimicry-llm`](../../../packages/openmimicry-llm/) | Token-stream completions from any LiteLLM-compatible provider; `LLMRouter` chooses primary vs. fallback. |
| **AvatarDirector** | [`openmimicry-avatar`](../../../packages/openmimicry-avatar/) `(./director.py)` | State machine that turns `RuntimeEvent`s into `AvatarDirective`s. The visible "mood" of the avatar. |
| **detect_task_intent** | [`openmimicry-tasks`](../../../packages/openmimicry-tasks/) `(./intent.py)` | Regex-first classifier that routes user text to LLM-vs-task. |
| **SpeechController** | `openmimicry-voice/voice/controllers/speech.py` | Coordinates STT + TTS — owns the single TTS task, barge-in policy, PTT cycle, live-wake projection. Cognition that bridges sensor and effector. |
| **TaskRouter** | `openmimicry-tasks/router.py` | Capability-based selection across registered `TaskRuntimeAdapter`s. |

## Contracts they satisfy

- `openmimicry.core.contracts.llm.LLMAdapter`
- `openmimicry.core.contracts.avatar.AvatarDirector`
- `openmimicry.core.contracts.avatar.AvatarOrchestrator`
- `openmimicry.core.contracts.voice.SpeechController`
- `openmimicry.core.contracts.tasks.TaskRuntimeAdapter` (the router
  satisfies this too, so it composes transparently)

## Why it spans multiple packages

The director's state machine belongs with the avatar runtimes
because it produces `AvatarDirective`s. The intent classifier
belongs with the task runtimes because it produces `TaskRequest`s.
Splitting cognition into its own package would just move state
away from the components that consume it. The Protocol surface in
`openmimicry-core` is what makes cognition feel like one layer
anyway.

## Develop it in isolation

```bash
# LLM router only — no real provider, no key
cd packages/openmimicry-llm
.venv\Scripts\python -m pytest tests/unit/llm/ -q

# Avatar director only — mocked runtime
cd packages/openmimicry-avatar
.venv\Scripts\python -m pytest tests/unit/avatar/test_director.py -q

# Intent classifier
.venv\Scripts\python -m pytest tests/unit/tasks/test_intent.py -q
```

## Adding a new LLM provider

Already supported via LiteLLM (any model string in the form
`provider/model` works). Adding a *non-LiteLLM* provider:

1. Implement `openmimicry.core.contracts.llm.LLMAdapter` in a new
   module.
2. Register it via entry point:

   ```toml
   [project.entry-points."openmimicry.contracts.llm"]
   yourpkg = "yourpkg.adapter:make_your_llm_adapter"
   ```

3. The contract test parametrises over every registered factory.

## Adding a new cognition step (e.g. a memory layer)

Cognition components communicate via the event bus, not direct
function calls. To add memory:

1. Subscribe to `LLMReplyComplete` events on the bus.
2. Publish a new `MemoryUpdated` event variant (additive amendment
   to `RuntimeEvent` — see `docs/contracts.md` §11).
3. The next chat turn's `LLMStarted` handler reads the memory and
   prepends it to the messages list.

Cognition is meant to be extended with new components, not new
imports. If you find yourself adding a `from openmimicry.tasks
import …` to your memory module, you're crossing a layer boundary
sideways — flip the dataflow through the bus instead.
