from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from .config import ExtractorConfig


@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float


@dataclass
class PixelCandle:
    x_center: int
    y_open: int
    y_high: int
    y_low: int
    y_close: int


class CandleExtractor:
    def __init__(self, config: ExtractorConfig):
        self.config = config

    def _mask(self, hsv: np.ndarray, low: tuple[int, int, int], high: tuple[int, int, int]) -> np.ndarray:
        mask = cv2.inRange(hsv, np.array(low), np.array(high))
        kernel = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    def extract_pixel_candles(self, frame_bgr: np.ndarray) -> List[PixelCandle]:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        bull = self._mask(hsv, self.config.bullish_hsv_low, self.config.bullish_hsv_high)
        bear = self._mask(hsv, self.config.bearish_hsv_low, self.config.bearish_hsv_high)
        merged = cv2.bitwise_or(bull, bear)

        contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candles: List[PixelCandle] = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < self.config.min_body_area:
                continue

            x, y, w, h = cv2.boundingRect(c)
            if w <= 1 or h <= 2:
                continue

            roi = merged[y : y + h, x : x + w]
            ys, xs = np.where(roi > 0)
            if len(ys) == 0:
                continue

            y_high = y + int(np.min(ys))
            y_low = y + int(np.max(ys))

            y_open = y
            y_close = y + h

            candle = PixelCandle(
                x_center=x + w // 2,
                y_open=y_open,
                y_high=y_high,
                y_low=y_low,
                y_close=y_close,
            )
            candles.append(candle)

        candles.sort(key=lambda c: c.x_center)
        return candles[-self.config.max_candles_per_frame :]

    def _pixel_to_price(self, y: int, height: int) -> float:
        pmin = self.config.price_min
        pmax = self.config.price_max
        if pmin is None or pmax is None or pmax <= pmin:
            # fallback to normalized pseudo-price
            return float(1.0 - (y / max(1, height)))
        frac = 1.0 - (y / max(1, height))
        return pmin + frac * (pmax - pmin)

    def extract_candles(self, frame_bgr: np.ndarray, timestamp: float) -> List[Candle]:
        height = frame_bgr.shape[0]
        px_candles = self.extract_pixel_candles(frame_bgr)
        candles: List[Candle] = []

        for c in px_candles:
            op = self._pixel_to_price(c.y_open, height)
            hi = self._pixel_to_price(c.y_high, height)
            lo = self._pixel_to_price(c.y_low, height)
            cl = self._pixel_to_price(c.y_close, height)
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=op,
                    high=max(hi, op, cl),
                    low=min(lo, op, cl),
                    close=cl,
                )
            )

        return candles
