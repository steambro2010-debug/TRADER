from __future__ import annotations

from collections import deque
from dataclasses import asdict
import statistics

import pandas as pd

from data_capture.candle_tracker import OHLC


class RollingOHLCBuffer:
    def __init__(self, maxlen: int = 1000, smooth_window: int = 3) -> None:
        self.items: deque[OHLC] = deque(maxlen=maxlen)
        self.smooth_window = smooth_window

    def append(self, candle: OHLC) -> bool:
        if any(v != v for v in [candle.open, candle.high, candle.low, candle.close]):
            return False
        if candle.high < candle.low:
            return False
        if abs(candle.high - candle.low) < 1e-6:
            return False

        self.items.append(candle)
        self._smooth_tail()
        return True

    def _smooth_tail(self) -> None:
        if len(self.items) < self.smooth_window:
            return
        tail = list(self.items)[-self.smooth_window :]
        last = self.items[-1]
        last.open = statistics.median([c.open for c in tail])
        last.high = statistics.median([c.high for c in tail])
        last.low = statistics.median([c.low for c in tail])
        last.close = statistics.median([c.close for c in tail])

    def __len__(self) -> int:
        return len(self.items)

    def to_df(self) -> pd.DataFrame:
        if not self.items:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "asset", "timeframe"])
        rows = []
        for c in self.items:
            d = asdict(c)
            d["asset"] = "QUOTEX"
            d["timeframe"] = "1m"
            rows.append(d)
        return pd.DataFrame(rows)
