# Module M13: `openmimicry-vision`

## Goal (1 line)

Ship an optional camera-driven `VisionAdapter` that detects hand landmarks and named gestures from the user's webcam and publishes `GestureDetected` / `HandPoseStarted` / `HandPoseEnded` events on the bus, which the avatar director maps to `AvatarDirective` overrides or task triggers.

Status: **post-v0.2**. Optional install (`pip install openmimicry[vision]`), opt-in via config (`vision.enabled: true`). Never required for any other module to compile, build, or test.

## Scope and non-scope

**In scope.**

- New Protocol `VisionAdapter` in `openmimicry.core.contracts.vision` (added via a contracts-amendment PR before M13 begins; see "Inputs").
- New frozen schemas in `openmimicry.core.schemas.vision`: `HandLandmark`, `HandPose`, `GestureDetection`, `VisionConfig`.
- Three new `RuntimeEvent` variants: `HandPoseStarted`, `HandPoseEnded`, `GestureDetected` (additive — bump no `schema_version`, just extend the union).
- `MediaPipeVisionAdapter` — webcam → MediaPipe Hands → 21-point landmarks → light-weight ONNX/scikit-learn classifier → gesture label.
- A `GestureClassifier` micro-interface so users can ship their own model (rule-based, scikit-learn, ONNX) without touching the adapter.
- `MockVisionAdapter` with a programmable `.push_gesture(name, hand, confidence)` for tests.
- Director-side mapping: a new section under `AvatarConfig` (or a peer `VisionConfig.gesture_map`) translating gesture names to `AvatarDirective` overrides (e.g. `wave -> {emotion: happy, gesture: "wave", duration_ms: 1200}`) and/or `TaskRequest` triggers.

**Non-scope.**

- Face detection, body pose, head-tracking. Body pose may come in a later module (M14 candidate); face landmarks are deliberately out — the project's user-wellbeing posture is that always-on face capture is a poor default.
- Multi-camera. One camera at a time; users with multiple webcams pick via `vision.camera_index`.
- Cloud vision APIs. The whole point of this module is to stay local-first. Cloud is left to third-party adapters that satisfy the Protocol.
- Audio. Voice is M2's job.
- Privacy/consent UX (toast on first activation, the `Indicator` overlay dot, the "vision off" hotkey). The shapes live in this brief; the wiring lives in M6 (backend) and M7 (frontend overlay).

## Inputs (immutable, from contracts.md)

This module **introduces** new frozen surface; therefore it is preceded by a **contracts-amendment PR** that lands the following before M13 begins:

```python
# openmimicry.core.schemas.vision  (new file, contracts.md §12)
class HandLandmark(BaseModel, frozen=True):
    x: float  # 0..1 normalised
    y: float  # 0..1 normalised
    z: float  # depth, relative

class HandPose(BaseModel, frozen=True):
    hand: Literal["left", "right"]
    landmarks: list[HandLandmark]   # exactly 21
    confidence: float

class GestureDetection(BaseModel, frozen=True):
    name: str                       # e.g. "wave", "thumbs_up", "open_palm"
    hand: Literal["left", "right", "both"]
    confidence: float
    pose: HandPose | None = None    # optional raw landmarks
    metadata: dict[str, Any] = {}

class VisionConfig(BaseModel, frozen=True):
    enabled: bool = False
    camera_index: int = 0
    target_fps: int = 15
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.6
    classifier: str = "default"     # name of registered GestureClassifier
    gesture_map: dict[str, dict] = {}   # gesture name -> partial AvatarDirective dict
```

```python
# openmimicry.core.schemas.events  — three new variants, additive
class HandPoseStarted(_Event):
    kind: Literal["hand_pose_start"] = "hand_pose_start"
    hand: Literal["left", "right"]

class HandPoseEnded(_Event):
    kind: Literal["hand_pose_end"] = "hand_pose_end"
    hand: Literal["left", "right"]

class GestureDetected(_Event):
    kind: Literal["gesture"] = "gesture"
    detection: GestureDetection
```

```python
# openmimicry.core.contracts.vision  (new file)
@runtime_checkable
class VisionAdapter(Protocol):
    name: str
    capabilities: set[str]     # e.g. {"hands", "gestures"}; future: {"body", "face"}

    async def start(self, config: VisionConfig) -> None: ...
    async def stop(self) -> None: ...

    @property
    def detections(self) -> AsyncIterator[GestureDetection]: ...
    @property
    def is_running(self) -> bool: ...

    async def healthcheck(self) -> bool: ...


@runtime_checkable
class GestureClassifier(Protocol):
    """Pure-function classifier: 21-point hand landmarks -> gesture name + confidence.

    Implementations may be rule-based, scikit-learn, ONNX, TF-lite. The
    adapter does not assume which.
    """
    name: str

    def classify(self, pose: HandPose) -> GestureDetection | None: ...
```

The contracts amendment PR also adds `vision: VisionConfig | None = None` to `AppConfig` (optional sub-config — absent means the whole subsystem is off).

## Outputs (this module owns)

```text
packages/openmimicry-vision/
  pyproject.toml
  README.md
  src/openmimicry/vision/
    __init__.py
    mocks.py                       # MockVisionAdapter, MockGestureClassifier
    adapters/
      __init__.py
      mediapipe_adapter.py         # MediaPipeVisionAdapter
    classifiers/
      __init__.py
      base.py                      # registry helpers
      rules.py                     # rule-based heuristics (default for the demo profile)
      sklearn.py                   # scikit-learn loader (.joblib)
      onnx.py                      # onnxruntime loader (.onnx)
    pipeline/
      __init__.py
      capture.py                   # OpenCV-backed video capture in a worker thread
      landmarks.py                 # MediaPipe Hands wrapper
      throttle.py                  # target_fps + debounce
    director_mapping.py            # gesture_map -> AvatarDirective hook (consumed by M3)
characters/
  octomimic/
    gestures/                      # optional pack-shipped gesture map example
      manifest.yaml
tests/unit/vision/
  test_pipeline.py
  test_classifiers_rules.py
  test_mediapipe_adapter.py        # uses recorded frames fixture
  test_director_mapping.py
```

Plus:

- `config/profiles/vision.yaml` — basic + voice + vision sample profile.
- `pyproject.toml` `[vision]` extras entry (and `[full]` += vision).
- `Makefile`: `make install PROFILE=vision` already works through the existing PROFILE machinery; nothing new in `Makefile` needed beyond a `make doctor` check for OpenCV / MediaPipe presence.
- `scripts/doctor.py`: add a soft check ("MediaPipe importable? webcam openable?") that warns when `vision.enabled=true` but the host can't satisfy.

## Mock implementations this module provides

```python
# openmimicry.vision.mocks
class MockVisionAdapter:
    """Programmable VisionAdapter.

    Call .push_gesture(name, hand="right", confidence=0.95) to drive the
    async stream. .push_pose(hand="right") emits HandPoseStarted/Ended pairs.
    """
    name = "mock"
    capabilities = {"hands", "gestures"}

    def __init__(self) -> None: ...
    def push_gesture(self, name: str, *, hand: str = "right",
                     confidence: float = 0.9) -> None: ...
    def push_pose(self, hand: str = "right") -> None: ...
    async def start(self, config: VisionConfig) -> None: ...
    async def stop(self) -> None: ...
    @property
    def detections(self) -> AsyncIterator[GestureDetection]: ...
    @property
    def is_running(self) -> bool: ...
    async def healthcheck(self) -> bool: ...


class MockGestureClassifier:
    """Returns a scripted sequence regardless of input."""
    name = "mock"
    def __init__(self, script: list[GestureDetection]) -> None: ...
    def classify(self, pose: HandPose) -> GestureDetection | None: ...
```

## Test surface

- **Unit.** `pipeline/throttle.py`: target_fps honoured, debounce ignores rapid duplicates.
- **Unit.** `classifiers/rules.py`: each shipped rule (`wave`, `thumbs_up`, `open_palm`, `fist`, `point`, `peace`) yields the expected name on a recorded landmark fixture.
- **Unit.** `mediapipe_adapter.py`: feed pre-recorded BGR frames from `tests/fixtures/vision/*.npy`, assert at least one `GestureDetected` on the bus stream. MediaPipe is import-time optional; tests `pytest.skip("mediapipe not installed")` cleanly.
- **Unit.** `director_mapping.py`: a `gesture_map` of `{"wave": {"emotion": "happy", "gesture": "wave", "duration_ms": 1200}}` produces the expected `AvatarDirective` when the corresponding `GestureDetected` arrives.
- **Contract.** Reuses Phase 0's contract-test machinery: `tests/contract/test_vision.py` parametrised over entry-point group `openmimicry.contracts.vision`. `MockVisionAdapter` registers itself; `MediaPipeVisionAdapter` registers when its extra is installed.
- **Integration.** `tests/integration/test_gesture_to_directive.py`: wire `MockVisionAdapter` + `AvatarDirector` (M3) + `MockAvatarRuntimeAdapter`, assert that `push_gesture("wave")` produces an `apply_directive(...)` call with `emotion="happy"`.

## Step-by-step plan (atomic, numbered)

1. Land the **contracts amendment PR**: `openmimicry.core.contracts.vision`, `openmimicry.core.schemas.vision`, three new event variants, `AppConfig.vision: VisionConfig | None`. Update `docs/contracts.md` with §12 (Vision) and add the events to §2.1. Bump no `schema_version` (additive).
2. Create `packages/openmimicry-vision/` with `pyproject.toml` (extras: `opencv-python-headless>=4.10`, `mediapipe>=0.10`, optional `onnxruntime>=1.18`, optional `scikit-learn>=1.5`).
3. Ship `MockVisionAdapter` and `MockGestureClassifier` in `mocks.py`. Register an entry-point under `openmimicry.contracts.vision`.
4. Implement `pipeline/capture.py` (OpenCV `VideoCapture` in a background `threading.Thread`, frames into an `asyncio.Queue`).
5. Implement `pipeline/landmarks.py` (MediaPipe Hands wrapper, 21-point landmarks per detected hand).
6. Implement `pipeline/throttle.py` (target_fps + per-gesture debounce).
7. Implement `classifiers/rules.py` with 6–8 useful default rules. Document them in `README.md`.
8. Implement `classifiers/sklearn.py` and `classifiers/onnx.py` as opt-in loaders.
9. Implement `adapters/mediapipe_adapter.py` wiring capture → landmarks → classifier → detection stream → bus.
10. Implement `director_mapping.py`: a hook that subscribes to `GestureDetected` and, given the `vision.gesture_map`, calls `AvatarDirector.apply_override(directive)` (a new optional method on `AvatarDirector` added by M3's next minor; for M13 we publish a "fake" `GestureToDirective` event the M3 director can read).
11. Add `config/profiles/vision.yaml` (basic + mock voice + MediaPipe vision + sample `gesture_map`).
12. Wire `make doctor` checks for OpenCV / MediaPipe / camera index.
13. Write the unit + integration + contract tests in "Test surface".
14. `CHANGELOG.md`: `### Added — M13 (openmimicry-vision) MediaPipe-based hand and gesture detection (optional).`
15. PR: `feat(vision): M13 — MediaPipe vision adapter, classifier registry, director mapping`. Labels: `module:vision`, `post-v0.2`.

## Definition of done (checklist)

- [ ] Contracts amendment PR landed first; `from openmimicry.core import VisionAdapter, GestureDetection, GestureDetected` succeeds.
- [ ] `pip install openmimicry[vision]` pulls the MediaPipe stack and only that.
- [ ] `MockVisionAdapter` works without any cv2/mediapipe installed.
- [ ] `MediaPipeVisionAdapter` passes the contract test on a host with a webcam OR on the CI matrix using a pre-recorded frame fixture.
- [ ] Rule-based classifier recognises `wave`, `thumbs_up`, `open_palm`, `fist`, `point`, `peace` on the fixture suite with confidence ≥ 0.8.
- [ ] The bus carries `GestureDetected` and the avatar reacts according to `vision.gesture_map`.
- [ ] `make doctor` warns clearly when `vision.enabled=true` but MediaPipe is missing.
- [ ] `vision.enabled` defaults to `false`; nothing camera-related runs unless the user opts in.
- [ ] The first time vision is enabled in the desktop app, a one-shot consent dialog appears (M7 owns the UI; this brief stops at "emit a `ConsentRequired` event the frontend can render").
- [ ] `CHANGELOG.md` has the M13 entry.
- [ ] `make ci` green on Ubuntu (headless capture, pre-recorded fixtures) + Windows.

## Privacy and consent posture

This module captures continuous video. Three guard rails are non-negotiable:

1. **Off by default.** `VisionConfig.enabled = False` is the schema default; no other module turns it on automatically.
2. **Explicit consent.** On first activation, the backend publishes a `ConsentRequired` event (variant added in the same contracts amendment PR) and refuses to start the pipeline until the frontend confirms.
3. **No upload, ever.** The frames never leave the process. The default classifier is local. Cloud classifiers are allowed via the `GestureClassifier` Protocol, but the adapter logs a clear `WARNING` at startup naming the destination, and the consent dialog includes a "cloud" badge.

These rules belong in `SECURITY.md` once M13 lands.

## Recommended LLM brief (copy-pasteable prompt)

> You are implementing **Module M13 (`openmimicry-vision`)** of OpenMimicry — an optional camera-driven gesture-detection module.
>
> Read these files first, in order:
>
> 1. `docs/contracts.md` (post-amendment — must include §12 "Vision" and the three vision event variants).
> 2. `docs/modules/M13_vision.md` — this brief.
> 3. `docs/avatar_modalities.md` §3 (AvatarDirective shape) and `docs/event_flows.md` (how gestures should flow into the director).
> 4. `docs/architecture.md` §11 (avatar directives).
>
> Implement the 15-step plan. Use `opencv-python-headless`, `mediapipe`, and (optionally) `onnxruntime` or `scikit-learn`. No other dependencies.
>
> Constraints:
>
> - Do not edit `packages/openmimicry-core/src/openmimicry/core/contracts/` or `.../schemas/` — those are frozen. The contracts amendment lands separately, before this brief begins.
> - `vision.enabled` defaults to `false`. Never auto-enable.
> - Frames must never leave the process. Cloud classifiers, if added, must log a startup warning naming the destination.
> - The `MockVisionAdapter` MUST run without OpenCV or MediaPipe installed (importing those at the top of `mocks.py` is a bug).
>
> Open the PR titled `feat(vision): M13 — MediaPipe vision adapter, classifier registry, director mapping` with every Definition-of-done item ticked.
