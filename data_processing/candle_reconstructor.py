from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    asset: str
    timeframe: str


class CandleBuffer:
    def __init__(self, maxlen: int = 1200) -> None:
        self.buffer: deque[Candle] = deque(maxlen=maxlen)

    def push_from_packet(self, packet: dict[str, Any]) -> Candle | None:
        candle = self._extract_candle(packet)
        if candle is None:
            return None
        self.buffer.append(candle)
        return candle

    def _extract_candle(self, packet: dict[str, Any]) -> Candle | None:
        payload = packet.get("payload", {})
        if not isinstance(payload, dict):
            return None

        candidate = payload.get("candle") or payload.get("kline") or payload.get("bar")
        if isinstance(candidate, list) and len(candidate) >= 6:
            return Candle(
                timestamp=float(candidate[0]),
                open=float(candidate[1]),
                high=float(candidate[2]),
                low=float(candidate[3]),
                close=float(candidate[4]),
                volume=float(candidate[5]),
                asset=str(payload.get("asset", "UNKNOWN")),
                timeframe=str(payload.get("timeframe", "1m")),
            )
        if isinstance(candidate, dict):
            required = {"timestamp", "open", "high", "low", "close"}
            if not required.issubset(candidate):
                return None
            return Candle(
                timestamp=float(candidate["timestamp"]),
                open=float(candidate["open"]),
                high=float(candidate["high"]),
                low=float(candidate["low"]),
                close=float(candidate["close"]),
                volume=float(candidate.get("volume", 0.0)),
                asset=str(candidate.get("asset", payload.get("asset", "UNKNOWN"))),
                timeframe=str(candidate.get("timeframe", payload.get("timeframe", "1m"))),
            )
        return None

    def as_dataframe(self) -> pd.DataFrame:
        cols = ["timestamp", "open", "high", "low", "close", "volume", "asset", "timeframe"]
        if not self.buffer:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([c.__dict__ for c in self.buffer], columns=cols)
