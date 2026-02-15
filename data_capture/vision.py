from __future__ import annotations

from dataclasses import dataclass
import time

import cv2
import numpy as np


@dataclass
class CandleCandidate:
    x: int
    y: int
    w: int
    h: int
    wick_top: int
    wick_bottom: int


class CandleVisionProcessor:
    def __init__(self, min_height: int = 8, body_min_width: int = 3, body_max_width: int = 30, debug: bool = False) -> None:
        self.min_height = min_height
        self.body_min_width = body_min_width
        self.body_max_width = body_max_width
        self.debug = debug

    def detect(self, frame: np.ndarray) -> tuple[list[CandleCandidate], np.ndarray, float]:
        t0 = time.perf_counter()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 40, 120)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[CandleCandidate] = []

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h < self.min_height:
                continue
            if not (self.body_min_width <= w <= self.body_max_width):
                continue
            ratio = h / max(w, 1)
            if ratio < 1.5:
                continue
            if w <= 2 and h > frame.shape[0] * 0.5:
                continue

            roi = edges[:, max(0, x - 1) : min(frame.shape[1], x + w + 1)]
            ys, _ = np.where(roi > 0)
            if len(ys) == 0:
                wick_top = y
                wick_bottom = y + h
            else:
                wick_top = int(np.min(ys))
                wick_bottom = int(np.max(ys))

            candidates.append(CandleCandidate(x=x, y=y, w=w, h=h, wick_top=wick_top, wick_bottom=wick_bottom))

        candidates.sort(key=lambda it: it.x)

        dbg = frame.copy()
        if self.debug:
            for c in candidates:
                cv2.rectangle(dbg, (c.x, c.y), (c.x + c.w, c.y + c.h), (64, 200, 255), 1)
                cv2.line(dbg, (c.x + c.w // 2, c.wick_top), (c.x + c.w // 2, c.wick_bottom), (0, 255, 180), 1)

        return candidates, dbg, (time.perf_counter() - t0) * 1000
