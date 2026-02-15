from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class CandleSignal:
    is_new_candle: bool
    shift_x: float
    ohlc: Tuple[float, float, float, float]


class CandleDetector:
    def __init__(self, shift_threshold: float, logger) -> None:
        self.shift_threshold = shift_threshold
        self.logger = logger
        self.prev_gray: Optional[np.ndarray] = None

    def process(self, frame: np.ndarray) -> CandleSignal:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        shift_x = 0.0
        is_new = False
        if self.prev_gray is not None:
            (dx, _), _ = cv2.phaseCorrelate(np.float32(self.prev_gray), np.float32(gray))
            shift_x = float(dx)
            is_new = abs(shift_x) >= self.shift_threshold

        self.prev_gray = gray
        ohlc = self._extract_ohlc(gray)
        return CandleSignal(is_new_candle=is_new, shift_x=shift_x, ohlc=ohlc)

    def _extract_ohlc(self, gray: np.ndarray) -> Tuple[float, float, float, float]:
        h, w = gray.shape
        last_slice = gray[:, int(w * 0.86) : int(w * 0.98)]
        col_profile = 255 - np.mean(last_slice, axis=1)
        high_idx = int(np.argmax(col_profile))
        low_idx = int(np.argmin(col_profile))

        open_band = gray[:, int(w * 0.82) : int(w * 0.86)]
        close_band = gray[:, int(w * 0.95) : int(w * 0.99)]

        open_val = float(np.mean(255 - open_band))
        close_val = float(np.mean(255 - close_band))
        high_val = float(h - high_idx)
        low_val = float(h - low_idx)

        high = max(open_val, close_val, high_val)
        low = min(open_val, close_val, low_val)
        return (open_val, high, low, close_val)
