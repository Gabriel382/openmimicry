# Working on one layer at a time

The whole point of the layered architecture is that you can pick up
*one* package, work on it for an afternoon, and ship a change without
spinning up the entire stack. This page is the operating manual for
that.

## The mock-first loop

Every layer ships a mock that satisfies its Protocol with zero
optional dependencies. The development loop is always the same:

1. **Open one package's directory.** Don't `cd` to the repo root.
   You're working on `packages/openmimicry-vision/`, not
   "OpenMimicry".
2. **Run only that package's tests.** Every test that needs a
   collaborator uses the *Mock* version. No real LLM, no microphone,
   no Tauri, no FastAPI.
3. **Iterate until the unit + contract tests are green.**
4. **Then** plug your change into `apps/backend/wiring.py`,
   `make backend`, and try the live stack.

That last step is the *only* one that touches anything outside your
package's directory.

## Step-by-step examples

### "I want to add a thumbs-down gesture"

You're in the sensor layer. You don't need an LLM, you don't need
Tauri, you don't need a microphone.

```bash
cd packages/openmimicry-vision

# 1. Add the new rule in src/openmimicry/vision/classifiers/gestures.py
# 2. Add unit tests in tests/unit/vision/test_gesture_classifier.py
.venv\Scripts\python -m pytest tests/unit/vision/test_gesture_classifier.py -q

# 3. The contract test auto-discovers your registered classifier:
.venv\Scripts\python -m pytest tests/contract/test_vision_gesture_classifier.py -q
```

Once both green, you're done — no other package needs to change.
The gesture name flows into `RuntimeEvent.GestureDetected` and the
director picks it up automatically.

### "I want to add an Ollama-shaped LLM provider"

LiteLLM already routes Ollama — no work needed. If you're adding a
non-LiteLLM provider:

```bash
cd packages/openmimicry-llm

# 1. Implement openmimicry.core.contracts.llm.LLMAdapter in
#    src/openmimicry/llm/yourprovider.py
# 2. Register a factory in pyproject.toml's
#    [project.entry-points."openmimicry.contracts.llm"]
# 3. Mock the HTTP call in tests/unit/llm/test_yourprovider.py
.venv\Scripts\python -m pytest tests/unit/llm/ -q

# 4. The contract test parametrises over every registered factory:
.venv\Scripts\python -m pytest tests/contract/test_llm_adapter.py -q
```

### "I want to add a new avatar runtime (e.g. Spine animations)"

You're in the effector layer. The 17-step template lives in
`docs/modules/M9_avatar_threejs.md` — that's the worked example to
mirror.

```bash
# Python side
cd packages/openmimicry-avatar
.venv\Scripts\python -m pytest tests/unit/avatar/runtimes/ -q

# Frontend side
cd apps/desktop/frontend
pnpm --filter @openmimicry/desktop-frontend exec vitest run src/runtimes/spine
```

You never need to touch the cognition layer. The director only
emits Protocol-shaped directives; your runtime decides how to render
them.

### "I want to change how the speech bubble looks"

You're in the surface layer. Backend can stay mocked.

```bash
make backend            # one terminal — uses MockLLM, mocks all voice
make frontend           # another terminal — Vite dev server
```

Edit `apps/desktop/frontend/src/components/SpeechBubble.tsx` and
watch Vite hot-reload.

### "I want to refactor the director state machine"

You're in the cognition layer. Director state machine is in
`packages/openmimicry-avatar/src/openmimicry/avatar/director.py`.

```bash
cd packages/openmimicry-avatar
.venv\Scripts\python -m pytest tests/unit/avatar/test_director.py -q
```

The director's tests use a *Mock* `AvatarRuntimeAdapter` and a
*Mock* `EventBus`. You don't need anything else.

## Anti-patterns

- **Editing across packages in one PR for the same feature.** If
  your change needs `openmimicry-vision` *and*
  `openmimicry-avatar` updated at the same time, you're probably
  changing a contract. Split the PR: contract change in
  `openmimicry-core` first, then the implementation changes can
  ship independently.
- **Importing a sibling package.** If you find yourself writing
  `from openmimicry.llm import …` inside `openmimicry-tts`, stop.
  Flip the dataflow through the bus. `scripts/check_imports.py`
  will fail your PR anyway.
- **Adding a "just one quick thing" to `wiring.py` from inside a
  unit test.** Wiring is a surface, not a fixture. Unit tests
  build their own dependency graph from mocks.

## The "is this in the right layer?" smell test

When in doubt, ask: **what is this code *doing*?**

| If it… | It lives in |
|--------|-------------|
| observes the user / world | Sensors |
| decides what to do next | Cognition |
| acts on the user / world | Effectors |
| transports data over a wire or paints pixels | Surfaces |
| defines a Protocol, schema, event, or config field | Foundation |

If a single function does two of those, it's the wrong abstraction.
Split it.
