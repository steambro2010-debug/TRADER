from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generator, Optional, Tuple

import cv2
import mss
import numpy as np


@dataclass
class FramePacket:
    timestamp: float
    frame_bgr: np.ndarray


class ScreenCapture:
    def __init__(self, monitor_index: int = 1, fps_target: int = 12) -> None:
        self.monitor_index = monitor_index
        self.fps_target = fps_target
        self._sct = mss.mss()

    def select_region(self) -> Tuple[int, int, int, int]:
        monitor = self._sct.monitors[self.monitor_index]
        raw = np.array(self._sct.grab(monitor))
        frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        cv2.namedWindow("Select Chart ROI", cv2.WINDOW_NORMAL)
        roi = cv2.selectROI("Select Chart ROI", frame, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select Chart ROI")
        x, y, w, h = [int(v) for v in roi]
        if w <= 0 or h <= 0:
            raise ValueError("Invalid ROI selected")
        return x, y, w, h

    def stream(self, region: Tuple[int, int, int, int]) -> Generator[FramePacket, None, None]:
        x, y, w, h = region
        monitor = {"left": x, "top": y, "width": w, "height": h}
        frame_interval = 1.0 / max(1, self.fps_target)

        while True:
            start = time.time()
            raw = np.array(self._sct.grab(monitor))
            frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
            yield FramePacket(timestamp=start, frame_bgr=frame)
            elapsed = time.time() - start
            sleep_for = frame_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
