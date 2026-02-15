from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Optional

import cv2
import mss
import numpy as np


@dataclass
class FramePacket:
    frame: np.ndarray
    ts: float


class ScreenCapture:
    def __init__(self, region: tuple[int, int, int, int] | None = None, target_fps: int = 15) -> None:
        self.region = region
        self.target_fps = target_fps
        self.monitor: Optional[dict[str, int]] = None
        self._sct = mss.mss()

    def set_region(self, left: int, top: int, width: int, height: int) -> None:
        self.region = (left, top, width, height)

    def _resolve_monitor(self) -> dict[str, int]:
        if self.region:
            l, t, w, h = self.region
            return {"left": l, "top": t, "width": w, "height": h}
        return self._sct.monitors[1]

    def grab(self) -> FramePacket:
        monitor = self._resolve_monitor()
        shot = np.array(self._sct.grab(monitor))
        frame = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
        return FramePacket(frame=frame, ts=time.time())

    async def stream(self):
        delay = 1.0 / max(self.target_fps, 1)
        while True:
            start = time.perf_counter()
            yield self.grab()
            elapsed = time.perf_counter() - start
            if elapsed < delay:
                await __import__("asyncio").sleep(delay - elapsed)
