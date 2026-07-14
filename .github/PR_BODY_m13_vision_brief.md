# docs(vision): add M13 brief and optional `vision` install extras

Adds **M13 (`openmimicry-vision`)** to the parallel-execution plan as an optional, post-v0.2 module. **No production code lands in this PR** — only the brief, the install plumbing, and a CHANGELOG note. The vision implementation itself is gated behind a contracts-amendment PR (also called out in the brief).

## What's in the brief

- A camera-driven `VisionAdapter` that publishes `GestureDetected` / `HandPoseStarted` / `HandPoseEnded` events on the bus. The avatar director maps gestures to `AvatarDirective` overrides — e.g. `wave -> {emotion: happy, gesture: "wave", duration_ms: 1200}` — or to `TaskRequest` triggers.
- Targets MediaPipe Hands for 21-point landmarks plus a pluggable `GestureClassifier` Protocol (rule-based, scikit-learn, ONNX).
- A `MockVisionAdapter` with `push_gesture(...)` so M3 / M6 can write integration tests without a webcam.
- New contract surface (lands via a separate contracts-amendment PR):
  - `openmimicry.core.contracts.vision`: `VisionAdapter`, `GestureClassifier`.
  - `openmimicry.core.schemas.vision`: `HandLandmark`, `HandPose`, `GestureDetection`, `VisionConfig`.
  - Three additive `RuntimeEvent` variants.
  - Optional `AppConfig.vision: VisionConfig | None`.

## Privacy posture

Three guard rails are non-negotiable and called out in the brief and in the future `SECURITY.md` update:

1. **Off by default** — `VisionConfig.enabled = False`; nothing else turns it on.
2. **Explicit consent** — first activation emits a `ConsentRequired` event the frontend renders; the pipeline refuses to start until the user confirms.
3. **No upload, ever** — frames stay in-process. Cloud classifiers, if added later, must log a startup `WARNING` naming the destination and the consent dialog must surface a "cloud" badge.

## Install plumbing in this PR

- `pyproject.toml`: new `vision` and `full-vision` optional-dependency groups.
- `Makefile`: `make install PROFILE=…` help now lists `vision` and `full-vision`; `install-workspace` runs `pip install -e packages/openmimicry-vision` **only** when the profile is `vision` or `full-vision` *and* the package directory exists, so the target is a no-op until M13 lands.
- `docs/modules/README.md`: new row for M13 at the bottom of the module table.
- `CHANGELOG.md`: a Documentation entry describing the brief + extras.

## Files

| File | What |
|---|---|
| `docs/modules/M13_vision.md` | New 230-line brief |
| `docs/modules/README.md` | M13 row added to module table |
| `pyproject.toml` | `vision` and `full-vision` optional extras |
| `Makefile` | `make install PROFILE=vision` documented and wired |
| `CHANGELOG.md` | Documentation note |

## Verification

- `pytest -q` — 119 passed, 22 skipped (no test changes).
- `ruff check`, `ruff format --check` — clean.
- `scripts/check_imports.py` — clean.
- No source files under `packages/*/src/` touched.

## Labels

`docs`, `module:vision`, `post-v0.2`
