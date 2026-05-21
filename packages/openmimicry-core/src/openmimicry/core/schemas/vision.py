"""Frozen Pydantic schemas for the vision subsystem (M13).

Designed for plug-in growth: the M13 module ships hands; M14+ can add
body and head without touching any schema field. The way this works:

* ``Landmark`` is a single 3D point shared by every detector.
* ``HandPose``, ``BodyPose``, ``HeadPose`` are concrete bundles —
  each with a fixed landmark count appropriate to its modality.
* ``VisionFrame`` is the top-level snapshot bundling all three. Any
  detector left ``None`` means "this modality didn't fire this tick".
* ``GestureDetection`` and ``MovementDetection`` are downstream
  classifier outputs.
* ``VisionConfig`` is the configuration surface, with one sub-block
  per detector and per classifier so future ones plug in by name.

Status: **Stable**, additive-only for one minor version. Bump
``schema_version`` only on a breaking change.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BodyPose",
    "GestureDetection",
    "HandLandmark",
    "HandPose",
    "HeadPose",
    "Landmark",
    "MovementDetection",
    "VisionClassifierConfig",
    "VisionConfig",
    "VisionDetectorConfig",
    "VisionFrame",
]


HandSide = Literal["left", "right", "both"]
"""Hand label (`"both"` only valid on aggregates / classifier outputs)."""


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class Landmark(BaseModel):
    """Single 3D landmark.

    Coordinates use the MediaPipe convention:

    * ``x`` and ``y`` are normalised to ``[0, 1]`` against the image
      width / height.
    * ``z`` is relative depth (smaller = closer to the camera), unitless.
    * ``visibility`` ∈ ``[0, 1]`` reports the detector's confidence
      that the landmark is in-frame. Optional — detectors that don't
      report it leave ``None``.
    * ``presence`` ∈ ``[0, 1]`` reports the detector's confidence
      that the body part exists at all (separate from visibility).

    Generic across modalities; the count + ordering of landmarks
    inside a higher-level pose is the modality's contract, not this
    schema's.
    """

    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float = 0.0
    visibility: float | None = None
    presence: float | None = None


# Backwards-compat alias requested by the M13 brief's example types.
HandLandmark = Landmark


# ---------------------------------------------------------------------------
# Poses (per-modality bundles)
# ---------------------------------------------------------------------------


class HandPose(BaseModel):
    """21-point MediaPipe Hands landmark bundle."""

    model_config = ConfigDict(frozen=True)

    hand: Literal["left", "right"]
    landmarks: list[Landmark]
    confidence: float = 1.0


class BodyPose(BaseModel):
    """33-point MediaPipe Pose landmark bundle.

    M13 ships the schema; concrete detectors land in M14. The schema
    exists now so downstream code (event bus, projection, director
    mapping) doesn't need amendment when body lands.
    """

    model_config = ConfigDict(frozen=True)

    landmarks: list[Landmark]
    confidence: float = 1.0


class HeadPose(BaseModel):
    """Coarse 6-DoF head pose plus optional sparse landmarks.

    Deliberately tiny — the project's privacy posture is that
    always-on face capture is a poor default. A face-mesh
    implementation can extend ``landmarks`` later; the rotation /
    translation fields are enough for gaze hints today.
    """

    model_config = ConfigDict(frozen=True)

    # Rotation, radians, around camera-space X/Y/Z.
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    # Centre of the head bbox in normalised image coords.
    center_x: float = 0.5
    center_y: float = 0.5
    # Optional sparse landmarks for downstream classifiers.
    landmarks: list[Landmark] = Field(default_factory=list)
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Top-level frame snapshot
# ---------------------------------------------------------------------------


class VisionFrame(BaseModel):
    """One full vision snapshot at a wall-clock instant.

    Detectors fill in only what they ran. ``hands`` is a list because
    MediaPipe Hands can return both hands in one tick.
    """

    model_config = ConfigDict(frozen=True)

    ts_ms: int = 0
    """Frame timestamp in milliseconds since the pipeline started."""

    image_width: int = 0
    image_height: int = 0

    hands: list[HandPose] = Field(default_factory=list)
    body: BodyPose | None = None
    head: HeadPose | None = None


# ---------------------------------------------------------------------------
# Classifier outputs
# ---------------------------------------------------------------------------


class GestureDetection(BaseModel):
    """Single classifier hit.

    ``modality`` says which detector produced the underlying pose
    (``"hand"`` for hand gestures, ``"body"`` for full-body poses,
    ``"head"`` for nods/shakes). ``source`` carries which classifier
    fired so the bus can be filtered downstream.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    """e.g. ``"wave"``, ``"thumbs_up"``, ``"open_palm"``, ``"nod"``."""

    modality: Literal["hand", "body", "head"] = "hand"
    hand: HandSide | None = None
    confidence: float = 1.0
    source: str = "default"
    """Which classifier fired (``"rules"`` / ``"sklearn"`` / ``"onnx"`` / ...)."""

    pose: HandPose | None = None
    """Optional raw landmarks — included when the consumer (director,
    panel UI) wants to project them. Heavy; default ``None``."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class MovementDetection(BaseModel):
    """Temporal classifier hit — recognises a *motion* across frames.

    Examples: ``"wave_motion"`` (hand sweeping left/right),
    ``"nodding"`` (head pitching), ``"shaking_head"`` (head yawing),
    ``"raised_hand"`` (sustained pose), ``"clap"``.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    modality: Literal["hand", "body", "head"] = "hand"
    hand: HandSide | None = None
    confidence: float = 1.0
    source: str = "default"
    duration_ms: int = 0
    """How long the movement has been continuously matched."""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class VisionDetectorConfig(BaseModel):
    """One entry under ``vision.detectors.<name>``.

    Concrete detectors (``hands`` / ``body`` / ``head``) consume their
    own keys via ``extra``. Only ``enabled`` is universal.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    enabled: bool = True
    """Disable the detector without removing its config block."""


class VisionClassifierConfig(BaseModel):
    """One entry under ``vision.gesture_classifiers.<name>`` or
    ``vision.movement_classifiers.<name>``.

    ``kind`` selects the backend: ``"rules"``, ``"sklearn"``,
    ``"onnx"``, or any third-party name registered via the
    ``openmimicry.contracts.vision_gesture_classifier`` /
    ``openmimicry.contracts.vision_movement_classifier`` entry-point
    groups.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    enabled: bool = True
    kind: str = "rules"
    path: str | None = None
    """Filesystem path for sklearn / onnx model files."""
    threshold: float = 0.6


class VisionConfig(BaseModel):
    """``vision:`` config block.

    Off by default. Even when ``enabled=True``, no camera opens until
    the consumer acknowledges :class:`ConsentRequired` (see
    ``docs/modules/M13_vision.md`` §"Privacy and consent posture").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    """**OFF by default.** The whole subsystem opts in here."""

    adapter: str = "mock"
    """Registered VisionAdapter name. ``"mock"`` ships with the
    package; ``"mediapipe"`` lights up when ``[vision]`` extras are
    installed."""

    camera_index: int = 0
    target_fps: int = 15
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.6
    require_consent: bool = True
    """When True (default), the adapter publishes
    :class:`ConsentRequired` and refuses to open the camera until the
    user confirms."""

    # Per-detector config — name → block. The MediaPipe adapter looks
    # up ``hands``, ``body``, ``head`` here.
    detectors: dict[str, VisionDetectorConfig] = Field(default_factory=dict)

    # Per-classifier config — name → block. Multiple classifiers can
    # run in parallel; their outputs all land on the bus.
    gesture_classifiers: dict[str, VisionClassifierConfig] = Field(default_factory=dict)
    movement_classifiers: dict[str, VisionClassifierConfig] = Field(default_factory=dict)

    # gesture_name -> partial AvatarDirective dict (consumed by the
    # director-mapping helper). Example::
    #
    #     wave:
    #       emotion: happy
    #       gesture: wave
    #       duration_ms: 1200
    gesture_map: dict[str, dict[str, Any]] = Field(default_factory=dict)
    movement_map: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # Free-form extras for third-party adapters that don't need a
    # contracts amendment to ship.
    extra: dict[str, Any] = Field(default_factory=dict)
