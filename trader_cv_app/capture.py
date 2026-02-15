from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class FramePacket:
    frame: np.ndarray
    timestamp: float


class ScreenCaptureThread(threading.Thread):
    def __init__(self, frame_queue: queue.Queue, roi: tuple[int, int, int, int], fps: int = 8):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.roi = roi
        self.fps = fps
        self._running = threading.Event()
        self._running.set()

    def stop(self) -> None:
        self._running.clear()

    def _grab_mss(self) -> Optional[np.ndarray]:
        try:
            import mss
        except ImportError:
            return None

        x, y, w, h = self.roi
        monitor = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            img = np.array(shot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def _grab_pyautogui(self) -> np.ndarray:
        import pyautogui

        x, y, w, h = self.roi
        image = pyautogui.screenshot(region=(x, y, w, h))
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def run(self) -> None:
        interval = 1.0 / max(self.fps, 1)
        while self._running.is_set():
            start = time.time()
            frame = self._grab_mss()
            if frame is None:
                frame = self._grab_pyautogui()

            packet = FramePacket(frame=frame, timestamp=start)
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(packet)
            elapsed = time.time() - start
            time.sleep(max(0.0, interval - elapsed))
