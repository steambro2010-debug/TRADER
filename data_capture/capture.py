from __future__ import annotations

import threading
import time
from typing import Callable

import cv2
import mss
import numpy as np


class ScreenRegionCapture:
    def __init__(self, region: tuple[int, int, int, int] | None, fps: int = 12) -> None:
        self._sct = mss.mss()
        self.region = region
        self.fps = max(1, min(fps, 15))
        self._running = False
        self._thread: threading.Thread | None = None

    def select_region_once(self) -> tuple[int, int, int, int]:
        full = np.array(self._sct.grab(self._sct.monitors[1]))
        frame = cv2.cvtColor(full, cv2.COLOR_BGRA2BGR)
        x, y, w, h = cv2.selectROI("Select Quotex Chart Region", frame, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow("Select Quotex Chart Region")
        self.region = (int(x), int(y), int(w), int(h))
        return self.region

    def _monitor(self) -> dict[str, int]:
        if self.region:
            x, y, w, h = self.region
            return {"left": x, "top": y, "width": w, "height": h}
        return self._sct.monitors[1]

    def start(self, on_frame: Callable[[np.ndarray, float], None]) -> None:
        if self._running:
            return
        self._running = True

        def loop() -> None:
            delay = 1.0 / self.fps
            while self._running:
                t0 = time.perf_counter()
                raw = np.array(self._sct.grab(self._monitor()))
                frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                on_frame(frame, time.time())
                dt = time.perf_counter() - t0
                if dt < delay:
                    time.sleep(delay - dt)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
