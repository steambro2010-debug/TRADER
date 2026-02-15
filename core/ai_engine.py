from __future__ import annotations

import time

from indicators.technical import compute_all
from ml_model.hybrid_model import HybridMLModel, Prediction
from strategy.signal_generator import SignalGenerator


class AIEngine:
    def __init__(self, predict_interval_seconds: int = 5, min_candles: int = 50) -> None:
        self.predict_interval_seconds = predict_interval_seconds
        self.min_candles = min_candles
        self.model = HybridMLModel()
        self.strategy = SignalGenerator()
        self.last_predict_ts = 0.0

    def maybe_predict(self, df, new_candle_closed: bool, force: bool = False):
        now = time.time()
        if len(df) < self.min_candles and not force:
            return None, "Collecting"
        if (not new_candle_closed) and (now - self.last_predict_ts < self.predict_interval_seconds) and not force:
            return None, "Waiting"

        feats = compute_all(df)
        self.model.fit(feats.tail(1200))
        pred: Prediction = self.model.predict(feats)
        sig = self.strategy.generate(feats, pred)
        self.last_predict_ts = now
        payload = {
            "direction": sig.direction,
            "confidence": sig.confidence,
            "prob_up": pred.prob_up,
            "prob_down": pred.prob_down,
            "model_mode": pred.model_name,
            "indicators": {
                "rsi": float(feats.iloc[-1].get("rsi_14", 0.0)),
                "macd_hist": float(feats.iloc[-1].get("macd_hist", 0.0)),
                "adx": float(feats.iloc[-1].get("adx_14", 0.0)),
                "volatility": float(feats.iloc[-1].get("volatility_10", 0.0)),
                "trend_bias": float(sig.indicator_bias),
            },
        }
        return payload, "Ready"
