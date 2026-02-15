from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml_model.hybrid_model import Prediction


@dataclass
class Signal:
    direction: str
    confidence: float
    model_probability: float
    indicator_bias: float
    diagnostics: dict[str, float]


class SignalGenerator:
    def indicator_bias(self, row: pd.Series) -> float:
        bullish = 0
        bearish = 0
        bullish += int(row["ema_9"] > row["ema_21"])
        bearish += int(row["ema_9"] <= row["ema_21"])
        bullish += int(row["macd"] > row["macd_signal"])
        bearish += int(row["macd"] <= row["macd_signal"])
        bullish += int(row["rsi_14"] > 50)
        bearish += int(row["rsi_14"] <= 50)
        bullish += int(row["stoch_k"] > row["stoch_d"])
        bearish += int(row["stoch_k"] <= row["stoch_d"])
        return (bullish - bearish) / max(bullish + bearish, 1)

    def generate(self, features: pd.DataFrame, prediction: Prediction) -> Signal:
        row = features.iloc[-1]
        bias = self.indicator_bias(row)
        model_up = prediction.prob_up / 100
        adjusted_up = min(max(model_up + (0.05 * bias), 0.0), 1.0)

        direction = "UP" if adjusted_up >= 0.5 else "DOWN"
        confidence = adjusted_up if direction == "UP" else (1 - adjusted_up)
        model_prob_direction = model_up if direction == "UP" else (1 - model_up)

        return Signal(
            direction=direction,
            confidence=confidence * 100,
            model_probability=model_prob_direction * 100,
            indicator_bias=bias,
            diagnostics={
                "prob_up": prediction.prob_up,
                "prob_down": prediction.prob_down,
                "rsi": float(row["rsi_14"]),
                "adx": float(row["adx_14"]),
            },
        )
