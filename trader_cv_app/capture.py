from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import mss
import numpy as np

from .data_models import FramePacket

logger = logging.getLogger(__name__)


@dataclass
class CaptureError:
    message: str
    fatal: bool = False


class ScreenCaptureWorker(threading.Thread):
    def __init__(
        self,
        frame_queue,
        error_queue,
        roi: tuple[int, int, int, int],
        fps: int = 15,
        resize_factor: float = 1.0,
    ):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.error_queue = error_queue
        self.roi = roi
        self.fps = fps
        self.resize_factor = resize_factor
        self._running = threading.Event()
        self._running.set()
        self._last_ts = time.time()

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        logger.info("Capture worker started with ROI=%s FPS=%s", self.roi, self.fps)
        interval = 1.0 / max(self.fps, 1)
        monitor = {
            "left": int(self.roi[0]),
            "top": int(self.roi[1]),
            "width": int(self.roi[2]),
            "height": int(self.roi[3]),
        }

        with mss.mss() as sct:
            while self._running.is_set():
                tick = time.time()
                try:
                    raw = sct.grab(monitor)
                    frame = np.asarray(raw)[:, :, :3]
                    frame = np.ascontiguousarray(frame)
                    if self.resize_factor != 1.0:
                        frame = cv2.resize(frame, None, fx=self.resize_factor, fy=self.resize_factor)
                    now = time.time()
                    fps = 1.0 / max(now - self._last_ts, 1e-6)
                    self._last_ts = now
                    packet = FramePacket(frame=frame, timestamp=now, fps=fps)

                    if self.frame_queue.full():
                        self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(packet)
                except Exception as exc:
                    logger.exception("Screen capture failed")
                    self.error_queue.put_nowait(CaptureError(message=f"Capture failed: {exc}", fatal=False))
                    time.sleep(0.2)

                elapsed = time.time() - tick
                sleep_for = interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)


def select_roi_interactive() -> tuple[int, int, int, int]:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        snap = np.asarray(sct.grab(monitor))[:, :, :3]

    preview = cv2.cvtColor(snap, cv2.COLOR_BGR2RGB)
    rect = cv2.selectROI("Select ROI", preview, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Select ROI")
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ValueError("ROI selection canceled.")
    return int(x), int(y), int(w), int(h)
