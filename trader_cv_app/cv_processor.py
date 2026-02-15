from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import List

import cv2
import numpy as np

from .data_models import Candle


class CandleDetector:
    """
    Heuristic candle extraction from chart pixels.
    Assumes green-ish bullish candles and red-ish bearish candles.
    """

    def __init__(self, max_candles: int = 200):
        self.max_candles = max_candles
        self._recent = deque(maxlen=max_candles)

    @staticmethod
    def _normalize_price(y: int, chart_h: int) -> float:
        return 1.0 - (y / max(chart_h - 1, 1))

    def detect(self, frame: np.ndarray) -> List[Candle]:
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        green_mask = cv2.inRange(hsv, (35, 40, 40), (95, 255, 255))
        red_mask1 = cv2.inRange(hsv, (0, 40, 40), (10, 255, 255))
        red_mask2 = cv2.inRange(hsv, (160, 40, 40), (180, 255, 255))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        candles: List[Candle] = []
        candles.extend(self._extract_from_mask(green_mask, frame, bullish=True, chart_h=h))
        candles.extend(self._extract_from_mask(red_mask, frame, bullish=False, chart_h=h))
        candles.sort(key=lambda c: c.timestamp)

        for c in candles:
            self._recent.append(c)
        return list(self._recent)

    def _extract_from_mask(self, mask: np.ndarray, frame: np.ndarray, bullish: bool, chart_h: int) -> List[Candle]:
        kernel = np.ones((3, 3), np.uint8)
        clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        result: List[Candle] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 2 or h < 5:
                continue

            wick_top = y
            wick_bottom = y + h
            body_top = y + int(0.2 * h)
            body_bottom = y + int(0.8 * h)

            open_px = body_bottom if bullish else body_top
            close_px = body_top if bullish else body_bottom
            high_px = wick_top
            low_px = wick_bottom

            candle = Candle(
                timestamp=datetime.utcnow(),
                open=self._normalize_price(open_px, chart_h),
                high=self._normalize_price(high_px, chart_h),
                low=self._normalize_price(low_px, chart_h),
                close=self._normalize_price(close_px, chart_h),
                bullish=bullish,
                body_top_px=body_top,
                body_bottom_px=body_bottom,
            )
            result.append(candle)
        return result
