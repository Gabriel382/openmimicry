"""Camera capture in a background thread.

``cv2`` is lazy-imported inside :class:`VideoCapture.start` so the
mocks suite — and the rest of this package — works without OpenCV
installed.

Frames are produced into an :class:`asyncio.Queue` whose
``maxsize`` defaults to 2 — when the consumer falls behind, the
**oldest** frame is dropped so the latency stays low. The producer
runs on a daemon ``threading.Thread`` and forwards frames into the
queue via the event loop's :meth:`call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from typing import Any

__all__ = ["CameraUnavailable", "VideoCapture"]


_log = logging.getLogger(__name__)


class CameraUnavailable(RuntimeError):
    """Raised when ``cv2`` is missing or the camera can't open."""


class VideoCapture:
    """OpenCV-backed video capture with an asyncio bridge.

    Parameters
    ----------
    camera_index
        ``cv2.VideoCapture`` index. ``0`` is usually the built-in
        webcam.
    target_fps
        Hint to the capture driver. Real FPS is best-effort.
    queue_size
        Bounded queue for produced frames; the oldest is dropped on
        full so latency stays low. Defaults to 2.
    backend
        Optional ``cv2`` backend hint (``cv2.CAP_DSHOW`` on Windows,
        for example). Forwarded to ``cv2.VideoCapture(index, backend)``.
    """

    def __init__(
        self,
        *,
        camera_index: int = 0,
        target_fps: int = 15,
        queue_size: int = 2,
        backend: int | None = None,
    ) -> None:
        self._camera_index = camera_index
        self._target_fps = max(1, target_fps)
        self._backend = backend
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=max(1, queue_size))
        self._thread: threading.Thread | None = None
        self._cap: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = threading.Event()
        self._closed = False

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def frames(self) -> asyncio.Queue[Any]:
        """Async queue producing ``ndarray`` BGR frames."""
        return self._queue

    async def start(self) -> None:
        """Open the camera and start the capture thread.

        Raises :class:`CameraUnavailable` when ``cv2`` is missing or
        the camera can't be opened. Idempotent.
        """
        if self._running.is_set():
            return
        try:
            cv2 = _import_cv2()
        except CameraUnavailable:
            raise
        args = (
            (self._camera_index, self._backend)
            if self._backend is not None
            else (self._camera_index,)
        )
        self._cap = cv2.VideoCapture(*args)
        if not self._cap.isOpened():
            self._cap = None
            raise CameraUnavailable(
                f"failed to open camera index {self._camera_index!r}; is another app using it?"
            )
        try:
            # Best-effort: drivers usually ignore these but don't error.
            self._cap.set(cv2.CAP_PROP_FPS, self._target_fps)
        except Exception as exc:
            _log.debug("VideoCapture: ignoring CAP_PROP_FPS error: %s", exc)

        self._loop = asyncio.get_running_loop()
        self._running.set()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="openmimicry.vision.capture",
            daemon=True,
        )
        self._thread.start()

    async def stop(self) -> None:
        """Stop the capture thread and release the camera. Idempotent."""
        self._closed = True
        self._running.clear()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)
        self._thread = None
        cap = self._cap
        if cap is not None:
            try:
                cap.release()
            except Exception as exc:
                _log.debug("VideoCapture: cap.release() raised: %s", exc)
        self._cap = None
        # Wake any consumer with a sentinel.
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
        self._loop = None

    # ------------------------------------------------------------- internals

    def _capture_loop(self) -> None:
        cap = self._cap
        loop = self._loop
        if cap is None or loop is None:
            return
        while self._running.is_set():
            try:
                ok, frame = cap.read()
            except Exception as exc:
                _log.warning("VideoCapture: cap.read() raised: %s", exc)
                break
            if not ok:
                _log.debug("VideoCapture: empty frame, continuing")
                continue
            # Push onto the asyncio queue from the capture thread.
            loop.call_soon_threadsafe(self._offer, frame)

    def _offer(self, frame: Any) -> None:
        # Drop oldest on full so latency stays low.
        try:
            self._queue.put_nowait(frame)
            return
        except asyncio.QueueFull:
            pass
        with contextlib.suppress(asyncio.QueueEmpty):
            self._queue.get_nowait()
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            _log.warning("VideoCapture: queue full after drop; frame lost")


def _import_cv2() -> Any:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise CameraUnavailable(
            'OpenCV is not installed. Install with `pip install "openmimicry-vision[mediapipe]"`.'
        ) from exc
    return cv2
