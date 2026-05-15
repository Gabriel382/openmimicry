# Character packs (Sprite2D modality)

A character pack is a self-contained folder that defines an avatar's identity: its name, voice preferences, default emotion, and a frame set per emotion. Packs are loaded at startup and validated by `openmimicry-avatar`.

This document specifies the pack format for the **Sprite2D** modality — the default, batteries-included rendering path. Other modalities have their own asset conventions (a `.vrm` or `.gltf` file for Three.js, a `.unitypackage` for Unity, etc.); the full modality matrix lives in [`avatar_modalities.md`](./avatar_modalities.md). The runtime sees only the normalized `AvatarDirective`; this doc explains how Sprite2D maps that directive to folders of frames.

## 1. Folder layout

```text
characters/
  octomimic/
    pack.yaml
    preview.png
    states/
      idle/             # one or more frames; played in order, looped
      idle_speaking/    # variant used when speaking == true
      listening/
      listening_speaking/
      thinking/
      thinking_speaking/
      speaking/         # used when emotion is explicitly "speaking"
      happy/
      happy_speaking/
      error/
      error_speaking/
```

The `_speaking` variant convention is intentional: every emotion has a "talking" sibling so the avatar can blend mouth animation into any emotional state without authoring a 2D rig. If a given `_speaking` folder is missing, the loader falls back to the base emotion (with a warning in the logs).

## 2. `pack.yaml`

```yaml
schema_version: 1
id: octomimic
name: Octomimic
author: "Gabriel <gabriel@example.com>"
license: CC-BY-4.0
preview: preview.png
default_state: idle           # one of: idle | listening | thinking | speaking | happy | error
default_emotion: neutral      # one of: neutral | happy | sad | angry | confused | focused | worried
transition_ms: 120

voice:
  preferred_engine: coqui
  preferred_voice: en_female_1

emotions:
  idle:
    frames: states/idle
    speaking_frames: states/idle_speaking
    fps: 8
    loop: true
  listening:
    frames: states/listening
    speaking_frames: states/listening_speaking
    fps: 10
    loop: true
  thinking:
    frames: states/thinking
    speaking_frames: states/thinking_speaking
    fps: 12
    loop: true
  speaking:
    frames: states/speaking
    speaking_frames: states/speaking
    fps: 14
    loop: true
  happy:
    frames: states/happy
    speaking_frames: states/happy_speaking
    fps: 12
    loop: false
    return_to: idle
    hold_ms: 1200
  error:
    frames: states/error
    speaking_frames: states/error_speaking
    fps: 10
    loop: false
    return_to: idle
    hold_ms: 1000
```

Notes:

- `frames` and `speaking_frames` can be a folder (sorted alphabetically) or an explicit list of file paths for fine-grained control.
- `return_to` and `hold_ms` are how the director knows to bounce out of one-shot emotions like `happy` and `error`.
- `voice.preferred_engine` and `preferred_voice` are *suggestions*. The TTS adapter resolves them against what is actually installed.

## 3. Loader

```python
# packages/openmimicry-avatar/src/openmimicry/avatar/loaders.py
def load_pack(pack_dir: Path) -> CharacterPack: ...
def list_packs(roots: list[Path]) -> list[CharacterPackSummary]: ...
```

`load_pack` validates the YAML against `PackSchema`, checks every referenced folder/file exists, computes frame counts, and warns on missing `_speaking` variants.

`scripts/validate_pack.py` exposes the same validator as a CLI so pack authors can run `python scripts/validate_pack.py characters/octomimic/`.

## 4. Director

`AvatarDirector.on_event(RuntimeEvent)` is a small state machine that emits a normalized `AvatarDirective`. The `state` field below corresponds to `AvatarDirective.state` (and Sprite2D maps it 1:1 to a folder name):

| state \ Event | UserSpeechStarted | LLMStarted | TTSStarted | TTSChunkSpoken | TTSFinished | Error | TaskCompleted |
|---|---|---|---|---|---|---|---|
| idle | listening | thinking | speaking* | — | — | error | happy |
| listening | — | thinking | speaking* | — | — | error | happy |
| thinking | listening | — | speaking* | — | idle | error | happy |
| speaking | listening | — | — | speaking | idle | error | happy |
| happy | listening | thinking | speaking* | — | — | error | — |
| error | listening | thinking | speaking* | — | — | — | — |

`speaking*` means the directive emits with `speaking=true`.

Hold-and-return states (`happy`, `error`) are handled by setting `directive.next_state` and `directive.duration_ms`; the orchestrator schedules the return-to-idle directive. Any newer event cancels the pending return.

The director also sets `directive.emotion` (`neutral` for most states, `happy` for `state=happy`, `worried` for `state=error`, configurable). Sprite2D ignores `emotion` unless the pack opts in; richer modalities use it as a separate dimension from `state`.

## 5. Speaking-variant decoupling

The frontend never tries to mix two folders at once. The directive is `{ emotion, speaking }`. The renderer picks `emotions[emotion].speaking_frames` if `speaking==true`, else `emotions[emotion].frames`. There is no per-frame blending — that is the whole point of authoring `_speaking` variants per emotion.

## 6. Fallback rules

The pack schema keys folders by **state** (idle / listening / thinking / speaking / happy / error). The `_speaking` sibling of each state folder is the talking variant.

- Missing `_speaking` for state S -> fall back to S's base frames; log once.
- Missing state S entirely -> fall back to `default_state`; log once.
- Manifest fails validation -> refuse to load, surface error on `/health`, frontend renders a placeholder.

These rules make a half-finished pack still demoable, which matters for portfolio contributors who want to drop in their own art.

## 7. Shipped packs

- `characters/octomimic/` — main demo character (already in repo).
- `characters/mimic_blue/` — secondary character used in tests and screenshots (already in repo).

Both already follow the emotion + emotion_speaking convention, so the migration to the new loader is a renaming/validation pass, not a re-authoring exercise.

## 8. Forward-compatibility with other modalities

This pack format is specifically the Sprite2D contract. The same `AvatarDirective` flows to every modality; only the renderer differs.

- `kind: "sprite2d"` (default) — this document.
- `kind: "advanced2d"` — Live2D / Spine / Rive packs; folder layout TBD per backend, validated by their adapter.
- `kind: "threejs"` / `"vrm"` / `"gltf"` — single asset file plus a small `pack.yaml` mapping emotions to clip names and expression presets.
- `kind: "unity"` — `pack.yaml` declares the Unity scene/prefab id and the parameter/trigger mapping the Unity bridge will set.
- `kind: "external"` — opaque to OpenMimicry; the third-party renderer owns its own asset format.

The full modality matrix and per-modality directive mapping is in [`avatar_modalities.md`](./avatar_modalities.md). The director, orchestrator, and bus protocol are identical across all of them.
