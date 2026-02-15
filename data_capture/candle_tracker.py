from __future__ import annotations

from dataclasses import dataclass
import statistics

from data_capture.vision import CandleCandidate


@dataclass
class OHLC:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleTracker:
    def __init__(self, timeframe_seconds: int = 60) -> None:
        self.timeframe_seconds = timeframe_seconds
        self.current: OHLC | None = None
        self.last_right_x: int | None = None
        self.last_spacing = 12.0

    def _estimate_spacing(self, candles: list[CandleCandidate]) -> float:
        if len(candles) < 3:
            return self.last_spacing
        deltas = [candles[i + 1].x - candles[i].x for i in range(len(candles) - 1)]
        valid = [d for d in deltas if d > 2]
        if not valid:
            return self.last_spacing
        self.last_spacing = float(statistics.median(valid))
        return self.last_spacing

    def update(self, candles: list[CandleCandidate], ts: float, frame_h: int) -> tuple[OHLC | None, OHLC | None]:
        if not candles:
            return None, self.current

        spacing = self._estimate_spacing(candles)
        right = candles[-1]

        high = float(frame_h - right.wick_top)
        low = float(frame_h - right.wick_bottom)
        body_top = float(frame_h - right.y)
        body_bottom = float(frame_h - (right.y + right.h))

        if self.current is None:
            open_ = body_bottom
            close = body_top
            self.current = OHLC(timestamp=ts, open=open_, high=high, low=low, close=close, volume=0.0)
            self.last_right_x = right.x
            return None, self.current

        if self.last_right_x is not None and right.x < self.last_right_x - (0.35 * spacing):
            closed = self.current
            self.current = OHLC(timestamp=ts, open=body_bottom, high=high, low=low, close=body_top, volume=0.0)
            self.last_right_x = right.x
            return closed, self.current

        cur = self.current
        cur.high = max(cur.high, high)
        cur.low = min(cur.low, low)
        cur.close = body_top if abs(body_top - cur.open) < abs(body_bottom - cur.open) else body_bottom
        self.last_right_x = right.x
        return None, cur
