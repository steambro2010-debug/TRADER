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

        if self.buffer and self.buffer[-1].timestamp == candle.timestamp:
            prev = self.buffer[-1]
            prev.high = max(prev.high, candle.high)
            prev.low = min(prev.low, candle.low)
            prev.close = candle.close
            prev.volume = candle.volume
            print(f"Candle buffer length: {len(self.buffer)}")
            return prev

        self.buffer.append(candle)
        print(f"Candle buffer length: {len(self.buffer)}")
        return candle

    def _extract_candle(self, packet: dict[str, Any]) -> Candle | None:
        payload = packet.get("payload", {})
        if not isinstance(payload, dict):
            return None

        candidate = payload.get("candle") or payload.get("kline") or payload.get("bar") or payload

        candle = self._from_list(candidate, payload)
        if candle is not None:
            return candle

        candle = self._from_dict(candidate, payload)
        if candle is not None:
            return candle

        tick = self._extract_tick(payload)
        if tick is None:
            return None
        return self._tick_to_candle(payload, tick)

    def _from_list(self, candidate: Any, payload: dict[str, Any]) -> Candle | None:
        if not isinstance(candidate, list) or len(candidate) < 5:
            return None
        volume = float(candidate[5]) if len(candidate) > 5 else 0.0
        return Candle(
            timestamp=float(candidate[0]),
            open=float(candidate[1]),
            high=float(candidate[2]),
            low=float(candidate[3]),
            close=float(candidate[4]),
            volume=volume,
            asset=str(payload.get("asset", "UNKNOWN")),
            timeframe=str(payload.get("timeframe", "1m")),
        )

    def _from_dict(self, candidate: Any, payload: dict[str, Any]) -> Candle | None:
        if not isinstance(candidate, dict):
            return None

        ts = self._pick(candidate, ["timestamp", "time", "ts", "t"])
        o = self._pick(candidate, ["open", "o"])
        h = self._pick(candidate, ["high", "h"])
        l = self._pick(candidate, ["low", "l"])
        c = self._pick(candidate, ["close", "c", "price"])
        if any(v is None for v in [ts, o, h, l, c]):
            return None

        volume = self._pick(candidate, ["volume", "v", "vol"]) or 0.0
        asset = self._pick(candidate, ["asset", "symbol"]) or payload.get("asset", "UNKNOWN")
        timeframe = self._pick(candidate, ["timeframe", "tf", "interval"]) or payload.get("timeframe", "1m")

        return Candle(
            timestamp=float(ts),
            open=float(o),
            high=float(h),
            low=float(l),
            close=float(c),
            volume=float(volume),
            asset=str(asset),
            timeframe=str(timeframe),
        )

    def _extract_tick(self, payload: dict[str, Any]) -> tuple[float, float] | None:
        tick_price = self._pick(payload, ["price", "last", "tick", "close", "c"])
        tick_ts = self._pick(payload, ["timestamp", "time", "ts", "t"])
        if tick_price is None or tick_ts is None:
            return None
        return float(tick_ts), float(tick_price)

    def _tick_to_candle(self, payload: dict[str, Any], tick: tuple[float, float]) -> Candle:
        tick_ts, tick_price = tick
        tf_seconds = self._parse_timeframe_seconds(str(payload.get("timeframe", "1m")))
        bucket_ts = tick_ts - (tick_ts % tf_seconds)

        if self.buffer and self.buffer[-1].timestamp == bucket_ts:
            prev = self.buffer[-1]
            prev.high = max(prev.high, tick_price)
            prev.low = min(prev.low, tick_price)
            prev.close = tick_price
            prev.volume = prev.volume + float(payload.get("volume", 0.0) or 0.0)
            return prev

        return Candle(
            timestamp=float(bucket_ts),
            open=tick_price,
            high=tick_price,
            low=tick_price,
            close=tick_price,
            volume=float(payload.get("volume", 0.0) or 0.0),
            asset=str(payload.get("asset", payload.get("symbol", "UNKNOWN"))),
            timeframe=str(payload.get("timeframe", "1m")),
        )

    def _pick(self, data: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return None

    def _parse_timeframe_seconds(self, timeframe: str) -> int:
        tf = timeframe.strip().lower()
        if tf.endswith("m") and tf[:-1].isdigit():
            return max(1, int(tf[:-1])) * 60
        if tf.endswith("s") and tf[:-1].isdigit():
            return max(1, int(tf[:-1]))
        if tf.endswith("h") and tf[:-1].isdigit():
            return max(1, int(tf[:-1])) * 3600
        return 60

    def as_dataframe(self) -> pd.DataFrame:
        cols = ["timestamp", "open", "high", "low", "close", "volume", "asset", "timeframe"]
        if not self.buffer:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([c.__dict__ for c in self.buffer], columns=cols)
