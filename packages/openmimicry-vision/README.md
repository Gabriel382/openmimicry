# openmimicry-vision (M13)

Optional, opt-in webcam → hand / body / head detection + gesture
and movement classification. Built on Google's MediaPipe and
designed to be **extended**: every detector and classifier is a
plug-in resolved via Python entry points, so M14+ can add new
modalities (face mesh, additional pose backends, third-party
gesture models) without touching this package.

> **Privacy posture**: vision is **off by default**. Even with
> `vision.enabled: true`, the camera does not open until
> `ConsentRequired` is acknowledged on the event bus. The pipeline
> never uploads frames; cloud classifiers (if added later) must
> log a startup warning naming the destination.

## Install

```bash
# minimal (mocks-only — works in CI without OpenCV or MediaPipe)
pip install -e packages/openmimicry-vision

# the full vision stack (webcam + MediaPipe Hands / Pose / Face)
pip install -e "packages/openmimicry-vision[mediapipe]"

# optional ML classifier backends
pip install -e "packages/openmimicry-vision[sklearn]"
pip install -e "packages/openmimicry-vision[onnx]"

# everything
pip install -e "packages/openmimicry-vision[full]"
```

`make install PROFILE=vision` does the workspace install + the
MediaPipe extras.

## What's in here

```
packages/openmimicry-vision/src/openmimicry/vision/
  mocks.py                                   # works without cv2/mediapipe
  adapters/mediapipe_adapter.py              # composes detectors + classifiers
  pipeline/
    capture.py                               # OpenCV VideoCapture (lazy)
    throttle.py                              # target_fps + per-gesture debounce
    detectors/{hands,body,head}.py           # MediaPipe Hands / Pose / Face
    detectors/__init__.py                    # registry (entry-point lookup)
  classifiers/
    rules.py                                 # default rule-based gesture classifier
    sklearn.py                               # joblib bundle loader
    onnx.py                                  # onnxruntime loader
    movements/rules.py                       # wave/nod/shake/raised_hand
  director_mapping.py                        # gesture/movement → AvatarDirective
```

## Modality coverage

| Detector       | Output                       | Status (M13)               |
|----------------|------------------------------|----------------------------|
| `mediapipe_hands` | 21-point hand skeleton (×2)  | **On by default**          |
| `mediapipe_pose`  | 33-point body skeleton       | Schema + detector shipped, **off by default** |
| `mediapipe_head`  | 6-DoF head pose + 6 keypoints | Schema + detector shipped, **off by default** |

The schemas (`HandPose`, `BodyPose`, `HeadPose`, `VisionFrame`) are
**frozen** as of M13. M14 only needs to flip `vision.detectors.body.enabled`
on, register a body-gesture classifier, and the bus carries new
`GestureDetected` / `MovementDetected` events with no contract
amendment.

## Default rule-based gesture classifier

Recognises six static hand poses on the MediaPipe Hands skeleton:

| Pose       | Required fingers extended | Confidence |
|------------|---------------------------|------------|
| `open_palm`| all                       | ≥ 0.9 |
| `fist`     | none                      | ≥ 0.8 |
| `thumbs_up`| thumb only                | ≥ 0.85 |
| `point`    | index only                | ≥ 0.85 |
| `peace`    | index + middle            | ≥ 0.85 |
| `wave_pose`| index + middle + ring + pinky (static pose used by `wave_motion`) | ≥ 0.8 |

Override or extend it via `vision.gesture_classifiers`:

```yaml
vision:
  gesture_classifiers:
    rules:
      enabled: true
      kind: rules
    custom_ml:
      enabled: true
      kind: onnx
      path: ~/.openmimicry/models/gestures.onnx
      labels: [wave, thumbs_up, peace]
      threshold: 0.7
```

## Movement (temporal) classifier

`classifiers/movements/rules.py` watches a short sliding window
of `VisionFrame`s and recognises:

* `wave_motion` — index-tip x oscillates ≥ 2 zero-crossings, amplitude ≥ 0.08.
* `raised_hand` — wrist stays above `raised_hand_y_threshold` (default 0.4).
* `nodding` — head pitch oscillates ≥ 2 zero-crossings, amplitude ≥ 0.15 rad.
* `shaking_head` — head yaw oscillates ≥ 2 zero-crossings, amplitude ≥ 0.18 rad.

All thresholds are constructor args — pass `RuleMovementClassifier(min_amplitude=...)`
to tighten or relax.

## Director mapping (gesture → AvatarDirective)

A small helper translates detections into avatar directives via the
`vision.gesture_map` / `vision.movement_map` config. The map keys
are gesture/movement names and the values are partial
`AvatarDirective` dicts. Example:

```yaml
vision:
  gesture_map:
    wave_pose: { emotion: happy, gesture: wave, duration_ms: 1200 }
    thumbs_up: { emotion: happy, gesture: thumbs_up, duration_ms: 900 }
  movement_map:
    wave_motion: { emotion: happy, gesture: wave, duration_ms: 1500, intensity: 0.8 }
    nodding:    { state: happy, emotion: happy, duration_ms: 600 }
    shaking_head:{ state: error, emotion: worried, duration_ms: 600 }
```

The helper is pure:

```python
from openmimicry.vision import directive_from_gesture
directive = directive_from_gesture(detection, gesture_map=cfg.gesture_map)
```

Returns `None` for unmapped gestures. Unknown keys in the override
dict are dropped (the only allowed keys are `AvatarDirective`'s real
fields).

## Extending — adding a new detector or classifier

Detectors and classifiers are resolved via three entry-point groups:

* `openmimicry.contracts.vision_detector`
* `openmimicry.contracts.vision_gesture_classifier`
* `openmimicry.contracts.vision_movement_classifier`

Register your factory in *your* package's `pyproject.toml`:

```toml
[project.entry-points."openmimicry.contracts.vision_detector"]
movenet_pose = "yourpkg.movenet:make_movenet_pose_detector"

[project.entry-points."openmimicry.contracts.vision_gesture_classifier"]
my_ml_classifier = "yourpkg.classifier:make_my_classifier"
```

Then point `vision.detectors.body.kind` or
`vision.gesture_classifiers.*.kind` at your name. The adapter does
the rest — no modification to this package needed.

## Privacy & consent (non-negotiable)

1. `VisionConfig.enabled = False` is the schema default. No other
   module turns it on.
2. When the adapter is asked to start with `require_consent=True`,
   it publishes `ConsentRequired` and waits for `ConsentResolved`
   before opening the camera. The frontend renders the consent
   dialog; until the user clicks "Allow", nothing camera-related
   happens.
3. Frames never leave the process. The default classifiers are
   local. Any cloud classifier registered through the entry-point
   group **must** log a clear `WARNING` at startup naming the
   destination — this is the convention, enforced by code review,
   not by the runtime.

See `docs/modules/M13_vision.md` and `SECURITY.md` for the full
policy.
