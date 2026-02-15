from __future__ import annotations

from dataclasses import dataclass
from collections import deque

import cv2
import numpy as np
import pandas as pd


@dataclass
class Candle:
    ts: float
    open: float
    high: float
    low: float
    close: float
    direction: str
    volume_proxy: float


class CandleReconstructor:
    """Approximate OHLC candles from chart pixels using segmentation + contour extraction."""

    def __init__(self, history_size: int = 500):
        self.history: deque[Candle] = deque(maxlen=history_size)

    def _segment(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        bullish = cv2.inRange(hsv, (35, 50, 50), (95, 255, 255))
        bearish = cv2.inRange(hsv, (0, 50, 50), (15, 255, 255))
        return bullish, bearish

    def _extract_candle_candidates(self, mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        edges = cv2.Canny(mask, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h > 8 and w > 2:
                boxes.append((x, y, w, h))
        return sorted(boxes, key=lambda b: b[0])

    def reconstruct_latest(self, frame: np.ndarray, ts: float) -> Candle | None:
        bullish, bearish = self._segment(frame)
        b_boxes = self._extract_candle_candidates(bullish)
        s_boxes = self._extract_candle_candidates(bearish)
        if not b_boxes and not s_boxes:
            return None

        candidates = [("UP", *box) for box in b_boxes] + [("DOWN", *box) for box in s_boxes]
        direction, x, y, w, h = sorted(candidates, key=lambda c: c[1])[-1]

        chart_h = frame.shape[0]
        high = float(chart_h - y)
        low = float(chart_h - (y + h))
        open_ = low if direction == "UP" else high
        close = high if direction == "UP" else low

        volume_proxy = float(np.count_nonzero(bullish | bearish) / frame.size)
        candle = Candle(ts=ts, open=open_, high=high, low=low, close=close, direction=direction, volume_proxy=volume_proxy)
        self.history.append(candle)
        return candle

    def as_dataframe(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "direction", "volume_proxy"])
        return pd.DataFrame([c.__dict__ for c in self.history])
