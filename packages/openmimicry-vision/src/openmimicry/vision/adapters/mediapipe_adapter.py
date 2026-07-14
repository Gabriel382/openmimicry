"""``MediaPipeVisionAdapter`` — composes pipeline + classifiers + bus.

Wiring:

1. :class:`VideoCapture` produces BGR frames in a background thread.
2. The configured detectors (hands / body / head) consume each
   frame; their outputs aggregate into a :class:`VisionFrame`.
3. Gesture classifiers consume hand poses; movement classifiers
   consume a sliding window of recent :class:`VisionFrame`s.
4. :class:`Throttle` honours ``target_fps``; :class:`Debouncer`
   suppresses rapid duplicates.
5. Detections land on :attr:`detections` and frames on :attr:`frames`.
   Tests subscribe to both directly; M6 wires them into the bus.

Heavy deps (``cv2``, ``mediapipe``, ``numpy``) live behind lazy
imports inside the detector modules. The adapter raises
:class:`MediaPipeVisionUnavailable` only when consent fails or all
configured detectors fail to warm up — partial detector failures
fall through with a single warning so the rest of the pipeline
keeps running.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from openmimicry.core.schemas import (
    BodyPose,
    GestureDetection,
    HandPose,
    HeadPose,
    MovementDetection,
    VisionConfig,
    VisionDetectorConfig,
    VisionFrame,
)

from ..classifiers.base import (
    ClassifierUnavailable,
    load_gesture_classifier,
    load_movement_classifier,
)
from ..pipeline import (
    Debouncer,
    DetectorUnavailable,
    Throttle,
    load_detector,
)
from ..pipeline.capture import CameraUnavailable, VideoCapture

__all__ = [
    "MediaPipeVisionAdapter",
    "MediaPipeVisionUnavailable",
    "make_mediapipe_vision_adapter",
]


_log = logging.getLogger(__name__)


class MediaPipeVisionUnavailable(RuntimeError):
    """Raised when consent is refused or the whole detector stack
    fails to warm up. Single-detector failures only log."""


_DEFAULT_DETECTORS: dict[str, str] = {
    "hands": "mediapipe_hands",
    "body": "mediapipe_pose",
    "head": "mediapipe_head",
}


class MediaPipeVisionAdapter:
    """Concrete vision adapter composing detectors + classifiers."""

    name: str = "mediapipe"

    def __init__(
        self,
        *,
        capture: VideoCapture | None = None,
        runtime_cfg: dict[str, Any] | None = None,
        consent_resolver: Any = None,
        window_size: int = 12,
    ) -> None:
        self.capabilities: set[str] = {"hands", "gestures", "movements"}
        self._runtime_cfg = dict(runtime_cfg or {})
        self._capture_override = capture
        self._consent_resolver = consent_resolver
        self._window_size = max(3, window_size)

        self._capture: VideoCapture | None = None
        self._config: VisionConfig | None = None
        self._task: asyncio.Task[None] | None = None
        self._detections: asyncio.Queue[GestureDetection | MovementDetection | None] = (
            asyncio.Queue()
        )
        self._frames: asyncio.Queue[VisionFrame | None] = asyncio.Queue()
        self._running: bool = False
        self._closed: bool = False

        # Detector + classifier instances (populated on start()).
        self._hands_detector: Any = None
        self._body_detector: Any = None
        self._head_detector: Any = None
        self._gesture_classifiers: list[Any] = []
        self._movement_classifiers: list[Any] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def detections(self) -> AsyncIterator[GestureDetection | MovementDetection]:
        return self._iter_detections()

    @property
    def frames(self) -> AsyncIterator[VisionFrame]:
        return self._iter_frames()

    async def healthcheck(self) -> bool:
        return not self._closed

    # ----------------------------------------------------------------- API

    async def start(self, config: VisionConfig) -> None:
        if self._running:
            return
        if self._closed:
            raise MediaPipeVisionUnavailable("adapter has been shut down")
        if not config.enabled:
            raise MediaPipeVisionUnavailable("vision.enabled is False; refusing to start")

        # Consent gate. Caller may supply a coroutine/callable that
        # resolves to True/False.
        if config.require_consent and self._consent_resolver is not None:
            try:
                granted = self._consent_resolver()
                if asyncio.iscoroutine(granted):
                    granted = await granted
            except Exception as exc:
                raise MediaPipeVisionUnavailable(f"consent_resolver raised: {exc}") from exc
            if not granted:
                raise MediaPipeVisionUnavailable("consent not granted; refusing to start")

        self._config = config
        self._build_detectors(config)
        self._build_classifiers(config)
        # Open the camera *after* detectors warm up to fail-fast.
        capture = self._capture_override or VideoCapture(
            camera_index=config.camera_index,
            target_fps=config.target_fps,
        )
        try:
            await capture.start()
        except CameraUnavailable as exc:
            raise MediaPipeVisionUnavailable(str(exc)) from exc
        self._capture = capture

        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="openmimicry.vision.mediapipe.loop")

    async def stop(self) -> None:
        self._running = False
        self._closed = True
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._capture is not None:
            with contextlib.suppress(Exception):
                await self._capture.stop()
            self._capture = None
        await self._shutdown_detectors()
        # Sentinels so consumers exit.
        await self._detections.put(None)
        await self._frames.put(None)

    # --------------------------------------------------------------- internals

    def _build_detectors(self, config: VisionConfig) -> None:
        detector_cfgs = config.detectors or {}
        # Hands.
        cfg = detector_cfgs.get("hands") or VisionDetectorConfig()
        if cfg.enabled:
            try:
                self._hands_detector = load_detector(
                    _DEFAULT_DETECTORS["hands"],
                    min_detection_confidence=config.min_detection_confidence,
                    min_tracking_confidence=config.min_tracking_confidence,
                )
            except DetectorUnavailable as exc:
                _log.warning("vision: hands detector unavailable: %s", exc)
        # Body.
        cfg = detector_cfgs.get("body") or VisionDetectorConfig(enabled=False)
        if cfg.enabled:
            try:
                self._body_detector = load_detector(
                    _DEFAULT_DETECTORS["body"],
                    min_detection_confidence=config.min_detection_confidence,
                    min_tracking_confidence=config.min_tracking_confidence,
                )
            except DetectorUnavailable as exc:
                _log.warning("vision: body detector unavailable: %s", exc)
        # Head.
        cfg = detector_cfgs.get("head") or VisionDetectorConfig(enabled=False)
        if cfg.enabled:
            try:
                self._head_detector = load_detector(
                    _DEFAULT_DETECTORS["head"],
                    min_detection_confidence=config.min_detection_confidence,
                )
            except DetectorUnavailable as exc:
                _log.warning("vision: head detector unavailable: %s", exc)

        if not any((self._hands_detector, self._body_detector, self._head_detector)):
            raise MediaPipeVisionUnavailable(
                "no detectors available — check `vision.detectors.*.enabled` "
                "and that the [mediapipe] extras are installed"
            )

    def _build_classifiers(self, config: VisionConfig) -> None:
        gesture_cfgs = config.gesture_classifiers or {}
        if not gesture_cfgs:
            # Default to rule-based gesture detection on hand poses.
            gesture_cfgs = {"default": _default_classifier_cfg("rules")}

        for cls_name, cls_cfg in gesture_cfgs.items():
            if not cls_cfg.enabled:
                continue
            extras = _classifier_extras(cls_cfg)
            try:
                classifier = load_gesture_classifier(cls_cfg.kind, **extras)
            except ClassifierUnavailable as exc:
                _log.warning(
                    "vision: gesture classifier %r (%s) unavailable: %s",
                    cls_name,
                    cls_cfg.kind,
                    exc,
                )
                continue
            self._gesture_classifiers.append(classifier)

        movement_cfgs = config.movement_classifiers or {}
        if not movement_cfgs:
            movement_cfgs = {"default": _default_classifier_cfg("rules")}
        for cls_name, cls_cfg in movement_cfgs.items():
            if not cls_cfg.enabled:
                continue
            extras = _classifier_extras(cls_cfg)
            try:
                classifier = load_movement_classifier(cls_cfg.kind, **extras)
            except ClassifierUnavailable as exc:
                _log.warning(
                    "vision: movement classifier %r (%s) unavailable: %s",
                    cls_name,
                    cls_cfg.kind,
                    exc,
                )
                continue
            self._movement_classifiers.append(classifier)

    async def _shutdown_detectors(self) -> None:
        for det in (self._hands_detector, self._body_detector, self._head_detector):
            if det is None:
                continue
            with contextlib.suppress(Exception):
                await det.shutdown()
        self._hands_detector = None
        self._body_detector = None
        self._head_detector = None
        self._gesture_classifiers.clear()
        self._movement_classifiers.clear()

    async def _run_loop(self) -> None:
        assert self._capture is not None
        assert self._config is not None
        # Warm up detectors before pulling frames so first detect
        # call doesn't allocate inside the hot loop.
        for det in (self._hands_detector, self._body_detector, self._head_detector):
            if det is None:
                continue
            try:
                await det.warmup()
            except Exception as exc:
                _log.warning(
                    "vision: detector %r warmup raised: %s",
                    getattr(det, "name", "?"),
                    exc,
                )

        throttle = Throttle(self._config.target_fps)
        debouncer = Debouncer()
        window: deque[VisionFrame] = deque(maxlen=self._window_size)
        ts_ms = 0
        frame_q = self._capture.frames

        while self._running:
            try:
                frame_bgr = await frame_q.get()
            except asyncio.CancelledError:
                raise
            if frame_bgr is None:
                break
            if not throttle.allow():
                continue
            ts_ms += throttle.interval_ms
            image_width, image_height = _frame_dims(frame_bgr)
            try:
                snapshot = await self._build_snapshot(
                    frame_bgr, ts_ms=ts_ms, w=image_width, h=image_height
                )
            except Exception as exc:
                _log.warning("vision: detector pass raised: %s", exc, exc_info=True)
                continue
            await self._publish_frame(snapshot)
            window.append(snapshot)
            await self._publish_gestures(snapshot, debouncer)
            await self._publish_movements(window, debouncer)

    async def _build_snapshot(self, frame_bgr: Any, *, ts_ms: int, w: int, h: int) -> VisionFrame:
        hands: list[HandPose] = []
        body: BodyPose | None = None
        head: HeadPose | None = None
        if self._hands_detector is not None:
            try:
                hands = await self._hands_detector.detect(frame_bgr)
            except Exception as exc:
                _log.warning("vision: hands detector raised: %s", exc)
        if self._body_detector is not None:
            try:
                body = await self._body_detector.detect(frame_bgr)
            except Exception as exc:
                _log.warning("vision: body detector raised: %s", exc)
        if self._head_detector is not None:
            try:
                head = await self._head_detector.detect(frame_bgr)
            except Exception as exc:
                _log.warning("vision: head detector raised: %s", exc)
        return VisionFrame(
            ts_ms=ts_ms,
            image_width=w,
            image_height=h,
            hands=hands,
            body=body,
            head=head,
        )

    async def _publish_frame(self, frame: VisionFrame) -> None:
        try:
            self._frames.put_nowait(frame)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._frames.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._frames.put_nowait(frame)

    async def _publish_gestures(self, frame: VisionFrame, debouncer: Debouncer) -> None:
        for hand in frame.hands:
            for classifier in self._gesture_classifiers:
                try:
                    detection = classifier.classify(hand)
                except Exception as exc:
                    _log.warning(
                        "vision: gesture classifier %r raised: %s",
                        getattr(classifier, "name", "?"),
                        exc,
                    )
                    continue
                if detection is None:
                    continue
                key = f"gesture:{detection.name}:{detection.hand or '?'}"
                if not debouncer.allow(key):
                    continue
                await self._offer_detection(detection)

    async def _publish_movements(self, window: deque[VisionFrame], debouncer: Debouncer) -> None:
        if len(window) < 3:
            return
        for classifier in self._movement_classifiers:
            try:
                detection = classifier.classify(list(window))
            except Exception as exc:
                _log.warning(
                    "vision: movement classifier %r raised: %s",
                    getattr(classifier, "name", "?"),
                    exc,
                )
                continue
            if detection is None:
                continue
            key = f"movement:{detection.name}:{detection.hand or detection.modality}"
            if not debouncer.allow(key):
                continue
            await self._offer_detection(detection)

    async def _offer_detection(self, detection: GestureDetection | MovementDetection) -> None:
        try:
            self._detections.put_nowait(detection)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._detections.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._detections.put_nowait(detection)

    async def _iter_detections(
        self,
    ) -> AsyncIterator[GestureDetection | MovementDetection]:
        while True:
            item = await self._detections.get()
            if item is None:
                return
            yield item

    async def _iter_frames(self) -> AsyncIterator[VisionFrame]:
        while True:
            item = await self._frames.get()
            if item is None:
                return
            yield item


def _default_classifier_cfg(kind: str) -> Any:
    from openmimicry.core.schemas import VisionClassifierConfig

    return VisionClassifierConfig(kind=kind)


def _classifier_extras(cfg: Any) -> dict[str, Any]:
    # Pull through the optional knobs the classifier factories accept.
    out: dict[str, Any] = {}
    for key in ("path", "labels", "threshold"):
        value = getattr(cfg, key, None)
        if value is not None:
            out[key] = value
    # `extra` is the pydantic ``extra="allow"`` overflow.
    try:
        for key, value in (cfg.model_extra or {}).items():
            out[key] = value
    except AttributeError:
        pass
    return out


def _frame_dims(frame: Any) -> tuple[int, int]:
    try:
        h = int(frame.shape[0])
        w = int(frame.shape[1])
        return w, h
    except Exception:
        return 0, 0


def make_mediapipe_vision_adapter(**kwargs: Any) -> MediaPipeVisionAdapter:
    """Entry-point factory."""
    return MediaPipeVisionAdapter(**kwargs)
