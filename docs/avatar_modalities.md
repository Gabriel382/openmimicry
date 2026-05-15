# Avatar modalities

OpenMimicry is not a 2D-sprite project with a chat layer attached. It is a modular avatar interface layer — the backend, LLM, voice, task delegation, personality, and event system stay the same, while the *visual frontend* is pluggable. Anything from a 360-pixel transparent PNG to a Unity-rendered companion can sit on top of the same runtime.

This document specifies the modalities OpenMimicry supports, the single `AvatarRuntimeAdapter` contract they all satisfy, and the normalized `AvatarDirective` schema the runtime emits. It is the companion to [`character_packs.md`](./character_packs.md) (which is the Sprite2D-specific pack format) and [`adapters.md`](./adapters.md) (which defines the contract alongside the other four).

## 1. The six modalities

### 1.1 Sprite 2D — `sprite2d`

The default, batteries-included modality. Frame-based PNG sequences served by the React overlay window in Tauri.

- transparent PNGs, frame sequences per emotion + emotion_speaking variant
- speech bubble, optional preview frame
- click-through background by default ([`desktop_overlay.md`](./desktop_overlay.md))
- no heavy engine dependency; ships with `[basic]` extras
- pack format documented in [`character_packs.md`](./character_packs.md)

This modality is the reference implementation of `AvatarRuntimeAdapter`. The other modalities are measured against it.

### 1.2 Advanced 2D — `advanced2d`

A family of richer 2D backends behind one adapter family. None of these are core dependencies; each is an optional adapter under `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/advanced2d/`.

- Live2D-style models (via web-side viewer in the overlay)
- Spine-style runtime animation
- Rive / Lottie / animated SVG
- Web Canvas / WebGL avatars

Capabilities: state-driven animation, expression mapping, speaking variants, configurable transitions, validation, optional lip-sync later. The core never imports Live2D, Spine, or Rive; it only knows the adapter.

### 1.3 Lightweight 3D — `threejs`, `vrm`, `gltf`

A web-stack 3D renderer running inside the Tauri overlay window: Three.js (default) or Babylon.js (optional swap). Loads VRM, glTF/GLB, FBX later if needed.

Capabilities:

- loading a 3D avatar file
- idle / listening / thinking / speaking animation clips
- emotion mapping to clip + expression preset
- configurable camera, lighting, background (transparent for overlay)
- optional head/eye/mouth animation later
- runs through `[threejs]` extras; no native engine install required

This is the main non-Unity 3D path. It's deliberately web-stack so the overlay can render it without a second window.

### 1.4 Live 3D — `live3d`

A richer 3D mode that consumes the full directive schema (gesture, gaze, intensity) and produces continuous animation rather than discrete clip swaps.

- realtime animation blending across clips
- procedural idle motion / breathing
- mouth movement from TTS audio (viseme stream or amplitude follow)
- gesture selection from emotional state
- gaze direction from text and / or user position
- optional webcam-based user awareness (later, opt-in)
- optional hand/face/body detection (later, opt-in)

Live 3D reuses the Three.js renderer in 1.3 but plugs in extra controllers (blender, mouth animator, gaze controller). It is a *configuration* of the lightweight 3D adapter, not a separate window — turning live mode on is a config flag, not a re-install.

### 1.5 Unity — `unity`

Unity is treated as a fully separate runtime that talks to OpenMimicry over a documented protocol. It is **never** a forced dependency of the Python package.

- Communication: WebSocket (default), HTTP, local TCP, or named pipes.
- The Unity sample project lives in a sibling repository or under `apps/unity/` as an optional folder, with its own `README.md`.
- Unity receives normalized `AvatarDirective`s and translates them to: Animator states, blend trees, facial expressions, gestures, camera transitions, scene events, UI overlays.
- Use cases: high-quality 3D characters, game-like companions, educational avatars, virtual doctors, museum guides, healthcare / rehabilitation pilots, XR extensions later.

Unity is an `AvatarRuntimeAdapter` like the others. The backend does not care that the wire is heavier; the adapter handles framing, ordering, and reconnection.

### 1.6 External — `external`

A catch-all for renderers OpenMimicry does not ship. The contract is the same; only the transport changes.

- VTube Studio-like systems
- Blender-based preview
- Unreal Engine integrations (later)
- browser-based avatar runtimes
- third-party desktop pet engines
- research prototypes

```
AvatarOrchestrator
    │
    ▼
AvatarRuntimeAdapter   (ExternalAvatarAdapter)
    │
    ▼
WebSocket / HTTP / TCP / named pipes
    │
    ▼
External renderer
```

The point is that someone with a Blender plugin and an afternoon can write an adapter against this contract and never touch OpenMimicry's core. That's the portfolio story.

## 2. `AvatarRuntimeAdapter` contract

```python
# packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/base.py
from typing import Protocol
from openmimicry.core.schemas.avatar import AvatarDirective

class AvatarRuntimeAdapter(Protocol):
    name: str
    capabilities: set[str]  # e.g. {"2d", "speaking_variants"}, {"3d", "gestures", "gaze"}

    async def load_character(self, character_id: str, config: dict) -> None:
        """Resolve and load the character resources. Must complete before
        the first apply_directive call. Idempotent for the same character_id."""

    async def apply_directive(self, directive: AvatarDirective) -> None:
        """Apply a normalized directive. Implementations decide how to map
        fields that don't apply to them (e.g. Sprite2D ignores gesture/gaze)."""

    async def set_text(self, text: str) -> None:
        """Update the speech bubble / caption surface (where applicable)."""

    async def start_speaking(self, text: str | None = None) -> None:
        """Hint that TTS playback has begun. Used by lip-sync / mouth-anim."""

    async def stop_speaking(self) -> None:
        """Hint that TTS playback has ended."""

    async def set_visibility(self, visible: bool) -> None:
        """Show or hide the avatar (overlay toggle, pause, etc.)."""

    async def healthcheck(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

Two implementation rules:

- Adapters MUST accept any well-formed `AvatarDirective` without raising; unsupported fields are ignored, not errors.
- Adapters MUST be cancellation-safe: a new `apply_directive` may arrive before the previous transition finishes, and the implementation is responsible for collapsing to the latest intent.

### 2.1 Concrete implementations

```text
Sprite2DAvatarAdapter        sprite2d                ships with [basic]
Advanced2DAvatarAdapter      live2d|spine|rive|...   ships with [advanced2d]
ThreeJSAvatarAdapter         threejs                 ships with [threejs]
VRMAvatarAdapter             vrm                     ships with [threejs]
Live3DAvatarAdapter          live3d                  ships with [threejs] + [live3d]
UnityAvatarAdapter           unity                   ships with [unity]
ExternalAvatarAdapter        external                ships with core (transport-only)
MockAvatarAdapter            mock                    ships with core (tests)
```

Each adapter lives under `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/<modality>/`. Heavy frontends (Three.js, Live2D viewers, Unity bridge clients) live in `apps/desktop/frontend/src/runtimes/<modality>/` and are invoked over the same projection wire — the Python adapter is thin and lets the browser do the rendering.

## 3. Normalized `AvatarDirective` schema

The directive is the contract the runtime emits. Every modality consumes it; lossy modalities drop fields silently. This replaces the simpler `{emotion, speaking, transition_ms}` shape used in earlier drafts.

```python
# packages/openmimicry-core/src/openmimicry/core/schemas/avatar.py
class AvatarDirective(BaseModel):
    state: Literal["idle", "listening", "thinking", "speaking", "happy", "error"]
    emotion: Literal[
        "neutral", "happy", "sad", "angry", "confused", "focused", "worried"
    ] = "neutral"
    animation: str | None = None        # adapter-specific clip/folder name
    speaking: bool = False
    text: str | None = None             # speech bubble / caption update
    next_state: str | None = None       # adapter hint: state to return to
    duration_ms: int | None = None
    intensity: float | None = None      # 0.0..1.0; for blending / strength
    gesture: str | None = None          # e.g. "wave", "shrug", "nod"
    gaze: str | None = None             # e.g. "towards_user", "down_left"
    metadata: dict[str, Any] = {}
```

Mapping by modality:

| Field | Sprite2D | Advanced 2D | Lightweight 3D | Live 3D | Unity | External |
|---|---|---|---|---|---|---|
| `state` | folder name (or fallback) | layer/state | clip group | clip group | Animator state | passed through |
| `emotion` | folder name | expression | morph/expression | morph + blend | parameter | passed through |
| `animation` | overrides folder | overrides clip | overrides clip | overrides clip | Animator trigger | passed through |
| `speaking` | picks `_speaking` folder | layer toggle | mouth driver | mouth driver | parameter | passed through |
| `text` | speech bubble | speech bubble | speech bubble | speech bubble | UI overlay | passed through |
| `next_state` | scheduler | scheduler | scheduler | scheduler | Animator transition | passed through |
| `duration_ms` | hold timer | hold timer | clip duration | blend window | timed transition | passed through |
| `intensity` | (ignored) | (often ignored) | (often ignored) | blend weight | parameter | passed through |
| `gesture` | (ignored) | one-shot layer | clip overlay | gesture controller | trigger | passed through |
| `gaze` | (ignored) | (ignored) | head/eye bones | gaze controller | parameter | passed through |
| `metadata` | (ignored) | (extension) | (extension) | (extension) | event payload | passed through |

Worked example (Live 3D consuming a richer directive):

```json
{
  "state": "speaking",
  "emotion": "happy",
  "animation": "happy_speaking",
  "speaking": true,
  "text": "Sure, let me try that.",
  "gesture": "wave",
  "gaze": "towards_user",
  "intensity": 0.7,
  "duration_ms": 2500
}
```

Sprite2D consumes the same directive but only acts on `state`, `speaking`, `animation` (folder name), `text`, `duration_ms`. Everything else is silently ignored — by design.

## 4. The `AvatarOrchestrator`

Between the runtime's event bus and the chosen `AvatarRuntimeAdapter` sits the `AvatarOrchestrator`. It is the only piece of glue that knows about both worlds.

```python
# packages/openmimicry-avatar/src/openmimicry/avatar/orchestrator.py
class AvatarOrchestrator:
    def __init__(
        self,
        director: AvatarDirector,        # event -> directive translator
        runtime: AvatarRuntimeAdapter,   # the chosen modality
        bus: EventBus,
        cfg: AvatarConfig,
    ): ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def swap_runtime(self, new_runtime: AvatarRuntimeAdapter) -> None: ...
```

`AvatarDirector` (see [`adapters.md`](./adapters.md)) translates `RuntimeEvent` into `AvatarDirective`. The orchestrator subscribes to the bus, asks the director for a directive, and passes it to the runtime. That keeps the director rendering-agnostic and the runtime event-agnostic.

`swap_runtime` lets the user change modality at runtime (e.g. switch from Sprite2D to Three.js for a demo) without restarting the backend.

## 5. Installation profiles

Install profiles map directly to `pip` extras and dictate which modalities and adapters are pulled in.

```toml
# pyproject.toml (workspace root)
[project.optional-dependencies]
basic = [
    "openmimicry-core",
    "openmimicry-avatar[sprite2d]",
    "openmimicry-llm[litellm]",
    "fastapi", "uvicorn",
]
voice = [
    "openmimicry[basic]",
    "openmimicry-voice[realtimestt,realtimetts]",
]
threejs = [
    "openmimicry[basic]",
    "openmimicry-avatar[threejs]",   # ships JS bundle entry-point in apps/desktop/frontend
]
live3d = [
    "openmimicry[threejs]",
    "openmimicry-avatar[live3d]",
]
unity = [
    "openmimicry[basic]",
    "openmimicry-avatar[unity]",     # protocol/bridge only; no Unity engine in pip
]
full = [
    "openmimicry[voice]",
    "openmimicry[threejs]",
    "openmimicry[live3d]",
    "openmimicry-tasks[mcp_agent,claude_code]",
]
studio = [
    "openmimicry[full]",
    "openmimicry-studio",            # editor tools, pack validators, asset converters
]
```

Profile intent table:

| Profile | What you get | Aimed at |
|---|---|---|
| `basic` | 2D sprite avatar, text chat via LiteLLM, Tauri overlay | First-time user, low install footprint |
| `voice` | basic + RealtimeSTT + RealtimeTTS | Hands-free demo, conference talks |
| `threejs` | basic + Three.js/VRM/glTF runtime | Portfolio screenshots, 3D demos |
| `live3d` | threejs + procedural motion, lip-sync, gaze | Research, education, livestream |
| `unity` | basic + protocol bridge to Unity sample app | Game-like companions, XR pilots |
| `full` | everything except editor tools | Maximalist setup, contributors |
| `studio` | full + character editor, pack validators, asset helpers | Pack authors, technical artists |

`make install PROFILE=threejs` translates to `uv pip install -e ".[threejs]"` plus the frontend bundle install.

## 6. Wiring summary

```text
            RuntimeEvent bus
                  │
                  ▼
           AvatarDirector
                  │
                  ▼            (chosen at startup via avatar.runtime config)
          AvatarRuntimeAdapter
          ┌───┬───┬───┬───┬───┬───┐
          │ 2D│Adv│3JS│Lv3│Uty│Ext│
          └───┴───┴───┴───┴───┴───┘
            │   │   │   │   │   │
            ▼   ▼   ▼   ▼   ▼   ▼
       Tauri overlay (sprite, advanced2d, threejs, live3d)
       WS/HTTP/TCP/pipes              (unity, external)
```

The backend emits one shape of directive. The orchestrator chooses where it goes. The frontends translate as much of it as they can.

## 7. Portfolio framing

The README and docs site lead with the modality table, not with "small desktop chatbot." A user should be able to read the README in under two minutes and understand:

- Start simple with a 2D avatar in minutes (`PROFILE=basic`).
- Upgrade to voice with one extra flag (`PROFILE=voice`).
- Swap to a 3D avatar without reinstalling the backend (`avatar.runtime: threejs`).
- Connect Unity through a documented protocol if the demo warrants it (`PROFILE=unity`).
- Wire external renderers, agents, and task runners through small adapter contracts.
- Use the **same core event system** for every modality.

That story is what makes the difference between "a desktop pet with an LLM" and "a modular avatar interface layer for LLMs, voice systems, and agentic task runtimes." The architecture in this document is designed so the second framing is honest.

## 8. Testing modalities

- Each runtime adapter ships with a contract test (`pytest.mark.avatar_runtime_contract`) that drives `load_character` + a fixed sequence of `apply_directive` calls and asserts no exceptions and the correct number of acks.
- `MockAvatarAdapter` records every directive and exposes it for assertion in integration tests.
- Frontend modalities (Three.js, sprite renderer) have Vitest tests that load a sample directive stream from a fixture file and snapshot the resulting DOM/Canvas state at known timestamps.
- Unity has a thin Python-side integration test that boots a `mock-unity-server` (a tiny WS echo) and asserts the adapter handles reconnects and out-of-order acks.

The result: adding a new modality means writing one adapter and passing one contract test. No core changes required.
