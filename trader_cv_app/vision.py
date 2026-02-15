from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np

from .data_models import Candle

logger = logging.getLogger(__name__)


class CandleVisionWorker(threading.Thread):
    def __init__(self, frame_queue, candle_queue, error_queue, max_candles: int = 100):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.candle_queue = candle_queue
        self.error_queue = error_queue
        self.max_candles = max_candles
        self._running = threading.Event()
        self._running.set()
        self._history = deque(maxlen=max_candles)

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        logger.info("Vision worker started")
        while self._running.is_set():
            try:
                packet = self.frame_queue.get(timeout=0.5)
            except Exception:
                continue

            try:
                detected = self._extract_frame_candles(packet.frame)
                self._merge_history(detected)
                payload = {
                    "frame": packet.frame,
                    "candles": list(self._history),
                    "fps": packet.fps,
                    "timestamp": packet.timestamp,
                }
                if self.candle_queue.full():
                    self.candle_queue.get_nowait()
                self.candle_queue.put_nowait(payload)
            except Exception as exc:
                logger.exception("Vision processing failed")
                self.error_queue.put_nowait({"type": "vision", "message": f"Vision failed: {exc}"})
                time.sleep(0.1)

    def _extract_frame_candles(self, frame: np.ndarray) -> list[Candle]:
        h, _ = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        bullish_mask = cv2.inRange(hsv, (35, 40, 40), (95, 255, 255))
        bearish_1 = cv2.inRange(hsv, (0, 40, 40), (10, 255, 255))
        bearish_2 = cv2.inRange(hsv, (160, 40, 40), (180, 255, 255))
        bearish_mask = cv2.bitwise_or(bearish_1, bearish_2)

        kernel = np.ones((2, 2), np.uint8)
        bullish_mask = cv2.morphologyEx(bullish_mask, cv2.MORPH_OPEN, kernel)
        bearish_mask = cv2.morphologyEx(bearish_mask, cv2.MORPH_OPEN, kernel)

        candles = []
        candles.extend(self._candles_from_mask(bullish_mask, True, h))
        candles.extend(self._candles_from_mask(bearish_mask, False, h))
        return sorted(candles, key=lambda c: c.x_center)

    def _candles_from_mask(self, mask: np.ndarray, bullish: bool, chart_h: int) -> list[Candle]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out: list[Candle] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 3 or h < 8:
                continue

            ys = np.where(mask[:, x : x + w] > 0)[0]
            if ys.size == 0:
                continue

            wick_top = int(ys.min())
            wick_bottom = int(ys.max())
            body_top = y
            body_bottom = y + h

            open_px = body_bottom if bullish else body_top
            close_px = body_top if bullish else body_bottom

            out.append(
                Candle(
                    timestamp=datetime.utcnow(),
                    open=self._normalize(open_px, chart_h),
                    high=self._normalize(wick_top, chart_h),
                    low=self._normalize(wick_bottom, chart_h),
                    close=self._normalize(close_px, chart_h),
                    bullish=bullish,
                    x_center=x + w // 2,
                )
            )
        return out

    @staticmethod
    def _normalize(y_px: int, chart_h: int) -> float:
        return float(1.0 - (y_px / max(chart_h - 1, 1)))

    def _merge_history(self, detected: list[Candle]) -> None:
        if not detected:
            self.error_queue.put_nowait({"type": "vision", "message": "No candles detected"})
            return

        newest = detected[-1]
        if not self._history:
            self._history.append(newest)
            return

        prev = self._history[-1]
        if abs(newest.close - prev.close) > 0.001 or newest.bullish != prev.bullish:
            self._history.append(newest)
