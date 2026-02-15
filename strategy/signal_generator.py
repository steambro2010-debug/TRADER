from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml_model.hybrid_model import Prediction


@dataclass
class Signal:
    direction: str
    confidence: float
    indicator_score: float
    pattern_score: float
    ml_score: float
    reason: str


class SignalGenerator:
    def _candlestick_pattern_score(self, df: pd.DataFrame) -> tuple[float, str]:
        if len(df) < 3:
            return 0.5, "insufficient pattern data"
        c = df.iloc[-1]
        p = df.iloc[-2]
        body = abs(c["close"] - c["open"])
        span = max(c["high"] - c["low"], 1e-9)
        upper_wick = c["high"] - max(c["close"], c["open"])
        lower_wick = min(c["close"], c["open"]) - c["low"]

        if body / span < 0.15:
            return 0.52, "doji"
        if c["close"] > c["open"] and p["close"] < p["open"] and c["close"] >= p["open"] and c["open"] <= p["close"]:
            return 0.78, "bullish engulfing"
        if c["close"] < c["open"] and p["close"] > p["open"] and c["open"] >= p["close"] and c["close"] <= p["open"]:
            return 0.22, "bearish engulfing"
        if lower_wick > body * 2 and upper_wick < body:
            return 0.7, "hammer"
        if upper_wick > body * 2 and lower_wick < body:
            return 0.3, "shooting star"
        return 0.5, "neutral candle"

    def _indicator_score(self, row: pd.Series) -> float:
        signals = []
        signals.append(1 if row["ema_9"] > row["ema_21"] else 0)
        signals.append(1 if row["macd"] > row["macd_signal"] else 0)
        signals.append(1 if row["close"] > row["bb_mid"] else 0)
        signals.append(1 if row["rsi_14"] < 70 else 0)
        signals.append(1 if row["stoch_k"] > row["stoch_d"] else 0)
        signals.append(1 if row["close"] > row["support"] else 0)
        signals.append(1 if row["adx_14"] > 20 else 0.5)
        return float(np.mean(signals))

    def generate(self, features: pd.DataFrame, ml_pred: Prediction) -> Signal:
        row = features.iloc[-1]
        indicator = self._indicator_score(row)
        pattern, reason = self._candlestick_pattern_score(features)
        ml_score = ml_pred.prob_up / 100

        confidence_up = (0.4 * indicator) + (0.2 * pattern) + (0.4 * ml_score)
        confidence = confidence_up * 100
        direction = "UP" if confidence_up >= 0.5 else "DOWN"
        if direction == "DOWN":
            confidence = (1 - confidence_up) * 100

        return Signal(
            direction=direction,
            confidence=float(confidence),
            indicator_score=indicator,
            pattern_score=pattern,
            ml_score=ml_score,
            reason=reason,
        )
