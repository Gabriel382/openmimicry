# OpenMimicry Unity Bridge

A minimal Unity sample that consumes `avatar.directive` JSON frames
from the OpenMimicry backend and drives a Unity `Animator`. The Python
adapter lives at `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/unity/`;
this folder ships the C# scripts that close the loop.

## What's in here

```
apps/unity-bridge/
  Assets/OpenMimicry/
    Scripts/
      WSClient.cs           # System.Net.WebSockets client + ack
      Directive.cs          # JsonUtility DTOs for every frame type
      AvatarController.cs   # maps directives -> Animator parameters
  README.md
```

CI does not build this project. The folder is intentionally a
"drop-in" — copy `Assets/OpenMimicry` into your Unity project (the
brief uses Unity 2022.3 LTS as the baseline; 2021+ also works).

## Quick start

1. Create a new Unity project and add the contents of
   `apps/unity-bridge/Assets/OpenMimicry/` to your project's
   `Assets/`.
2. Drop your character prefab into the scene and add an `Animator`
   with the parameters the bridge expects (`State` int, `Emotion`
   int, `Speaking` bool, `Gesture` trigger, `Intensity` float). The
   integer mappings live at the bottom of `AvatarController.cs`.
3. Add a new empty GameObject and attach both `WSClient` and
   `AvatarController` to it. Set `WSClient.url` to the backend's
   Unity-bridge endpoint (default `ws://127.0.0.1:8765`).
4. Run the OpenMimicry backend with `avatar.runtime: unity` and the
   Unity bridge server pointing at the same endpoint.
5. Press Play. Inbound frames advance the Animator in real time;
   outbound `ack` and `telemetry` frames flow back to the Python
   adapter automatically.

## Wire protocol

See the additive amendment in `docs/contracts.md` §9 and the M11
section of `docs/modules/post_v0_2_modalities.md`. Summary:

| Direction       | Frame `type`        | Purpose                                    |
|-----------------|---------------------|--------------------------------------------|
| backend → Unity | `avatar.directive`  | Animator parameters + gesture trigger.     |
| backend → Unity | `load.character`    | Hot-swap the active character.             |
| backend → Unity | `set.visibility`    | Toggle the renderer on/off.                |
| backend → Unity | `bubble.text`       | Mirror chat-bubble text on a UI label.     |
| Unity → backend | `ack` (`for: ...`)  | Per-directive backpressure ack.            |
| Unity → backend | `telemetry`         | `{fps, anim_state}` once per second.       |

## Build notes

* `System.Net.WebSockets` is available in Unity 2021+ when using the
  Mono or IL2CPP backends. Older Unity versions need a third-party
  WebSocket package; not covered here.
* The default WebSocket URL points at `127.0.0.1` so the bridge stays
  local. Change `WSClient.url` to a LAN address only if you trust the
  network; the wire protocol is not authenticated.
* The bridge runs the WS thread on a background `Task`. All inbound
  frames are marshalled back to the main thread before they touch
  any `Animator`, so the scripts are safe for use in standalone
  player builds.
