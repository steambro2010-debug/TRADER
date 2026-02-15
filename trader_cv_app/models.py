from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd

from .data_models import PredictionResult


@dataclass
class ModelWeights:
    xgb: float = 0.35
    rf: float = 0.35
    lstm: float = 0.30


class EnsemblePredictor:
    def __init__(self, sequence_length: int = 20):
        self.sequence_length = sequence_length
        self.weights = ModelWeights()
        self.xgb = None
        self.rf = None
        self.lstm = None

    def load(self, model_dir: str) -> None:
        base = Path(model_dir)
        xgb_path = base / "xgb.joblib"
        rf_path = base / "rf.joblib"
        lstm_path = base / "lstm.keras"

        if xgb_path.exists():
            self.xgb = joblib.load(xgb_path)
        if rf_path.exists():
            self.rf = joblib.load(rf_path)
        if lstm_path.exists():
            try:
                from tensorflow import keras

                self.lstm = keras.models.load_model(lstm_path)
            except Exception:
                self.lstm = None

    def predict(self, feature_df: pd.DataFrame) -> Optional[PredictionResult]:
        if feature_df.empty:
            return None

        ignore_cols = {"timestamp", "target"}
        model_cols = [c for c in feature_df.columns if c not in ignore_cols]
        last_row = feature_df[model_cols].iloc[[-1]]

        probs: Dict[str, float] = {}
        probs["xgb"] = self._predict_tree(self.xgb, last_row)
        probs["rf"] = self._predict_tree(self.rf, last_row)
        probs["lstm"] = self._predict_lstm(feature_df[model_cols])

        bullish = sum(getattr(self.weights, k) * probs[k] for k in probs)
        bearish = 1 - bullish
        confidence = abs(bullish - bearish)
        return PredictionResult(
            bullish_probability=float(np.clip(bullish, 0, 1)),
            bearish_probability=float(np.clip(bearish, 0, 1)),
            confidence=float(np.clip(confidence, 0, 1)),
            model_breakdown=probs,
        )

    @staticmethod
    def _predict_tree(model, row: pd.DataFrame) -> float:
        if model is None:
            return 0.5
        if hasattr(model, "predict_proba"):
            return float(model.predict_proba(row)[0][1])
        pred = model.predict(row)
        return float(pred[0])

    def _predict_lstm(self, data: pd.DataFrame) -> float:
        if self.lstm is None or len(data) < self.sequence_length:
            return 0.5
        seq = data.tail(self.sequence_length).to_numpy().reshape(1, self.sequence_length, data.shape[1])
        pred = self.lstm.predict(seq, verbose=0)
        return float(pred[0][0])
