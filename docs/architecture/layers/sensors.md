# Layer: Sensors / Captors

Anything that **observes** the user or the world. Pure inputs.
Sensors publish `RuntimeEvent`s on the bus; they never decide what
the avatar should do — that's the cognition layer's job.

## Packages

| Package | What it observes | Status |
|---------|------------------|--------|
| [`openmimicry-stt`](../../../packages/openmimicry-stt/) | Microphone → transcript (`UserSpeechStarted`, `UserSpeechFinal`, `TranscriptPreview`, `WakeDetected`) | Facade over the STT half of `openmimicry-voice`. |
| [`openmimicry-vision`](../../../packages/openmimicry-vision/) | Webcam → hand / body / head landmarks → gesture and movement events. **Off by default**, consent-gated. | Native package. |

(`openmimicry-voice` is still the source-of-truth implementation
package for both STT *and* TTS. `openmimicry-stt` re-exports the STT
adapters with their own package boundary so you can install / develop
the sensor layer without dragging the TTS deps in.)

## Contracts they satisfy

- `openmimicry.core.contracts.voice.STTAdapter`
- `openmimicry.core.contracts.voice.WakeController`
- `openmimicry.core.contracts.vision.VisionAdapter`
- `openmimicry.core.contracts.vision.{LandmarkDetector, HandDetector, BodyDetector, HeadDetector}`
- `openmimicry.core.contracts.vision.{GestureClassifier, MovementClassifier}`

## What lives here

- `MockSTTAdapter`, `RealtimeSTTAdapter` (wrap RealtimeSTT)
- `WakeController` (thin enable/disable wrapper for live-wake mode)
- `MockVisionAdapter`, `MediaPipeVisionAdapter`
- The vision detector + classifier registries (entry-point groups
  `openmimicry.contracts.vision_detector`,
  `vision_gesture_classifier`, `vision_movement_classifier`)
- Rule-based gesture classifier (open_palm, fist, thumbs_up, point,
  peace, wave_pose)
- Temporal movement classifier (wave_motion, raised_hand, nodding,
  shaking_head)
- The pipeline primitives: `VideoCapture` (OpenCV worker thread),
  `Throttle`, `Debouncer`

## What doesn't live here

- TTS — that's `openmimicry-tts`.
- The `SpeechController` (state machine that owns the barge-in policy)
  — that's cognition-ish but lives in `openmimicry-voice` today
  because it coordinates both STT and TTS.

## Develop it in isolation

```bash
# STT only
cd packages/openmimicry-stt
.venv\Scripts\python -m pytest tests/unit/voice/test_stt_mock.py -q

# Vision only
cd packages/openmimicry-vision
.venv\Scripts\python -m pytest tests/unit/vision/ -q
```

Both suites are hermetic — no microphone, no camera, no MediaPipe
install required. Everything is mocked at the Protocol boundary.

## Adding a new sensor

1. Implement the relevant Protocol from `openmimicry.core.contracts.*`.
2. Ship a mock that satisfies the Protocol with zero optional deps.
3. Register a factory via the right entry-point group in your
   `pyproject.toml`:

   ```toml
   [project.entry-points."openmimicry.contracts.vision_detector"]
   movenet_pose = "yourpkg.movenet:make_movenet_pose_detector"
   ```

4. The contract test in `tests/contract/` parametrises over every
   registered factory — your implementation will be exercised
   automatically.

5. No change needed in `apps/backend/wiring.py` *unless* you want
   the new sensor on by default in a profile (then add a wiring
   branch keyed on the config value).

See [`working_independently.md`](../working_independently.md) for the
full mock-first development loop.

## Privacy posture

Sensors are the most privacy-sensitive layer. Three rules apply:

1. **Off by default.** Vision's `enabled: false` schema default is
   non-negotiable. No other module turns it on automatically.
2. **Consent on first activation.** The adapter publishes
   `ConsentRequired` and refuses to open the camera until the
   frontend grants consent.
3. **No upload, ever.** Frames stay in-process. Any third-party
   classifier that ships later and *does* talk to a cloud must log
   a startup warning naming the destination — convention enforced
   by code review.
