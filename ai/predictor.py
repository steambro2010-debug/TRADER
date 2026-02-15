from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass
class Prediction:
    direction: str
    confidence: float
    indicators: Dict[str, float]
    mode: str
    up_probability: float
    down_probability: float


class Predictor:
    def __init__(self, model, logger) -> None:
        self.model = model
        self.logger = logger

    def predict(self, indicators: Dict[str, float]) -> Prediction:
        if self.model is not None:
            features = np.array(
                [[indicators["rsi"], indicators["macd"], indicators["adx"], indicators["volatility"], indicators["trend"]]],
                dtype=float,
            )
            probs = self.model.predict_proba(features)[0]
            down_prob, up_prob = float(probs[0]), float(probs[1])
            mode = "model"
        else:
            trend = indicators["trend"]
            macd = indicators["macd"]
            rsi = indicators["rsi"]
            score = (0.5 * trend) + (0.35 * np.tanh(macd)) + (0.15 * ((rsi - 50) / 50))
            up_prob = float(np.clip(0.5 + score, 0.01, 0.99))
            down_prob = 1.0 - up_prob
            mode = "heuristic"

        direction = "UP" if up_prob >= down_prob else "DOWN"
        confidence = max(up_prob, down_prob)
        return Prediction(
            direction=direction,
            confidence=confidence,
            indicators=indicators,
            mode=mode,
            up_probability=up_prob,
            down_probability=down_prob,
        )
