# feat(vision): M13 — openmimicry-vision (MediaPipe hand/body/head + classifier registry)

Implements `docs/modules/M13_vision.md` plus the contracts amendment
the brief requires. Optional, **off by default**; no other module
depends on this one.

## What lands

### Contracts amendment (additive, Stable — no `schema_version` bump)

`packages/openmimicry-core/src/openmimicry/core/schemas/vision.py`:

- `Landmark` (3D point + optional visibility/presence — generic
  across modalities).
- `HandPose` (21 pts, left/right), `BodyPose` (33 pts), `HeadPose`
  (6-DoF + sparse landmarks).
- `VisionFrame` — top-level snapshot bundling hands + body + head.
- `GestureDetection` and `MovementDetection` carry `modality`
  (`hand` / `body` / `head`) + `source` (which classifier fired).
- `VisionConfig` with `enabled` (default `False`), per-detector
  sub-blocks, per-classifier sub-blocks (`kind` + `path` + `threshold`
  + free extras), plus `gesture_map` / `movement_map`.

`packages/openmimicry-core/src/openmimicry/core/contracts/vision.py`:

- `VisionAdapter` — top-level Protocol.
- `LandmarkDetector` + specialisations `HandDetector`,
  `BodyDetector`, `HeadDetector`. Duck-typed: the adapter composes
  detectors without branching on modality.
- `GestureClassifier` / `MovementClassifier` Protocols.

Five new `RuntimeEvent` variants: `HandPoseStarted`, `HandPoseEnded`,
`GestureDetected`, `MovementDetected`, `ConsentRequired`,
`ConsentResolved`. All folded into the discriminated union.

`AppConfig.vision: VisionConfig | None`.

The amendment is **additive only**: every existing event /
schema field is untouched, `schema_version` stays at `1`.

### `openmimicry-vision` package

```
packages/openmimicry-vision/
  pyproject.toml                   # extras: mediapipe / sklearn / onnx / full
  README.md
  src/openmimicry/vision/
    mocks.py                       # importable without cv2/mediapipe
    adapters/mediapipe_adapter.py  # composes detectors + classifiers
    director_mapping.py            # gesture → AvatarDirective
    pipeline/
      capture.py                   # OpenCV VideoCapture in worker thread
      throttle.py                  # target_fps + per-key debounce
      detectors/{hands,body,head,base}.py
    classifiers/
      rules.py                     # default rule-based hand classifier
      sklearn.py                   # joblib bundle loader
      onnx.py                      # onnxruntime loader
      movements/rules.py           # wave / nod / shake / raised_hand
```

### Registries — `make stub, so future plug-ins are easy`

Three entry-point groups so M14+ can land new modalities without
touching this package:

```toml
[project.entry-points."openmimicry.contracts.vision_detector"]
mediapipe_hands = "openmimicry.vision.pipeline.detectors.hands:make_mediapipe_hands_detector"
mediapipe_pose  = "openmimicry.vision.pipeline.detectors.body:make_mediapipe_pose_detector"
mediapipe_head  = "openmimicry.vision.pipeline.detectors.head:make_mediapipe_head_detector"

[project.entry-points."openmimicry.contracts.vision_gesture_classifier"]
rules   = "openmimicry.vision.classifiers.rules:make_rule_classifier"
sklearn = "openmimicry.vision.classifiers.sklearn:make_sklearn_classifier"
onnx    = "openmimicry.vision.classifiers.onnx:make_onnx_classifier"

[project.entry-points."openmimicry.contracts.vision_movement_classifier"]
rules = "openmimicry.vision.classifiers.movements.rules:make_rule_movement_classifier"
```

A future MoveNet pose detector or a custom ONNX gesture model
plugs in by adding a single entry-point line; the adapter's
`load_detector(name)` / `load_gesture_classifier(name)` calls do
the rest.

### Coverage matrix (M13)

| Detector       | Output                       | Status                     |
|----------------|------------------------------|----------------------------|
| `mediapipe_hands` | 21-point hand skeleton (×2)  | **On by default**          |
| `mediapipe_pose`  | 33-point body skeleton       | Schema + detector shipped, off by default |
| `mediapipe_head`  | 6-DoF head pose + 6 keypoints | Schema + detector shipped, off by default |

The body and head schemas are frozen as of M13 — M14 only needs to
flip `vision.detectors.body.enabled` and ship a body-gesture
classifier.

### Default rule classifier

Six static hand gestures, each tested against a hand-crafted
21-point fixture:

| Pose       | Rule                                          | Confidence |
|------------|-----------------------------------------------|------------|
| `open_palm`| every finger extended                         | ≥ 0.9 |
| `fist`     | no finger extended                            | ≥ 0.8 |
| `thumbs_up`| only thumb extended                           | ≥ 0.85 |
| `point`    | only index extended                           | ≥ 0.85 |
| `peace`    | index + middle extended                       | ≥ 0.85 |
| `wave_pose`| four fingers extended (thumb optional)         | ≥ 0.8 |

### Movement classifier (temporal)

Sliding `VisionFrame` window → `MovementDetection`:

* `wave_motion` — index-tip x oscillates ≥ 2 zero-crossings with
  amplitude ≥ `min_amplitude`.
* `raised_hand` — wrist stays above `raised_hand_y_threshold`
  across ≥ 80 % of the window.
* `nodding` — head pitch oscillates ≥ 2 zero-crossings with
  amplitude ≥ `min_pitch_rad`.
* `shaking_head` — head yaw oscillates ≥ 2 zero-crossings with
  amplitude ≥ `min_yaw_rad`.

### Director mapping

`director_mapping.py` turns `GestureDetection` /
`MovementDetection` into `AvatarDirective` overrides via the
configured `gesture_map` / `movement_map`. Whitelisted keys only —
garbage fields drop with a debug log. Provenance lands in
`metadata.{vision_source, vision_confidence}` so consumers can
distinguish vision-driven directives from director-emitted ones.

### Privacy + consent (non-negotiable)

1. `VisionConfig.enabled = False` is the schema default.
2. When `require_consent=True`, the adapter publishes
   `ConsentRequired` and refuses to start until a consent
   callback / resolver returns `True`. The frontend will render
   the dialog (M7 follow-up; the bus event is in place now).
3. Frames never leave the process. Cloud classifiers (if added
   via the entry-point group) must log a startup WARNING naming
   the destination — code-review convention.

### Tests

`tests/unit/vision/`:

- `test_throttle.py` — `Throttle.allow()` honours fps, interval
  floor, reset; `Debouncer` per-key + cooldown + reset.
- `test_classifiers_rules.py` — every shipped gesture against
  21-point fixtures; rejects short landmark lists; populates
  `pose` reference.
- `test_movement_rules.py` — `wave_motion` zero-crossings,
  amplitude floor, `raised_hand` sustained pose, `nodding` &
  `shaking_head` with synthetic sinusoidal head poses, empty
  windows return `None`.
- `test_mocks.py` — Protocol satisfaction for every mock; mock
  adapter lifecycle; scripted gesture / movement streams; static
  assertion that `mocks.py` never imports `cv2` or `mediapipe`.
- `test_director_mapping.py` — whitelisted keys, unmapped → `None`,
  duration fallback, provenance metadata, default state.
- `test_mediapipe_adapter.py` — drives the adapter with a fake
  `VideoCapture` + fake hand detector (no MediaPipe import in the
  test path); proves the rule classifier sees `open_palm` end-to-
  end, the disabled-flag gates startup, the consent resolver
  refuses to start when it returns `False`, and frames carry
  landmarks even when classifiers are disabled.

`tests/contract/test_vision.py` — un-skipped, hermetic guard
`{"mock"}`. Round-trips `start → is_running → stop` and asserts
capabilities is a `set[str]`.

### Doctor + profile

`scripts/doctor.py` gains a vision section that warns when the
`openmimicry.vision` package isn't importable or when OpenCV /
MediaPipe are missing. Camera probe is opt-in via
`OPENMIMICRY_DOCTOR_PROBE_CAMERA=1` so `make doctor` doesn't yank
the webcam on by surprise.

`config/profiles/vision.yaml` — sample profile (basic + mock voice
+ MediaPipe vision + sample gesture/movement maps).

### Makefile

The existing `PROFILE=vision` branch already installs
`packages/openmimicry-vision` editable when the directory exists —
no Makefile change needed. `make install PROFILE=vision` is the
canonical setup command.

## Out of scope

- Body-pose gesture classifier (M14).
- Frontend consent dialog (M7 follow-up; the `ConsentRequired`
  event is on the bus and the adapter consumes a
  `consent_resolver` callback).
- Backend wiring (`apps/backend/.../wiring.py` doesn't pick up
  vision yet; that lands in a small wiring PR alongside M7's
  consent UI).
- Face mesh. Deliberately deferred — the privacy posture is that
  always-on face-mesh capture is a poor default. `HeadPose` ships
  a 6-DoF + sparse-landmark schema so a future mesh detector can
  extend `landmarks` without amending the contract.

Closes the M13 task.
