from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


try:
    from xgboost import XGBClassifier  # type: ignore
except Exception:  # pragma: no cover
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier  # type: ignore
except Exception:  # pragma: no cover
    LGBMClassifier = None

from sklearn.ensemble import RandomForestClassifier


@dataclass
class Prediction:
    prob_up: float
    prob_down: float
    model_name: str


class HybridMLModel:
    def __init__(self) -> None:
        self.model = self._build_model()
        self.feature_cols: list[str] = []
        self.fitted = False

    def _build_model(self):
        if XGBClassifier is not None:
            return XGBClassifier(n_estimators=120, max_depth=4, learning_rate=0.06, subsample=0.9, colsample_bytree=0.9)
        if LGBMClassifier is not None:
            return LGBMClassifier(n_estimators=160, learning_rate=0.05, num_leaves=31)
        return RandomForestClassifier(n_estimators=150, max_depth=6, random_state=42)

    def fit(self, features: pd.DataFrame) -> None:
        df = features.dropna().copy()
        if len(df) < 120:
            return
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
        df = df.dropna()

        ignore = {"ts", "direction", "target"}
        cols = [c for c in df.columns if c not in ignore]
        x = df[cols]
        y = df["target"]
        self.model.fit(x, y)
        self.feature_cols = cols
        self.fitted = True

    def predict(self, features: pd.DataFrame) -> Prediction:
        if (not self.fitted) or features.empty:
            return Prediction(50.0, 50.0, self.model.__class__.__name__)

        row = features[self.feature_cols].tail(1)
        probs = self.model.predict_proba(row)[0]
        up = float(probs[1] * 100)
        down = float(probs[0] * 100)
        return Prediction(prob_up=up, prob_down=down, model_name=self.model.__class__.__name__)
