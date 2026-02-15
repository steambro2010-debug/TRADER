from __future__ import annotations

from dataclasses import dataclass
import importlib.util

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier


@dataclass
class Prediction:
    prob_up: float
    prob_down: float
    model_name: str


class HybridMLModel:
    def __init__(self, advanced_lstm: bool = False) -> None:
        self.advanced_lstm = advanced_lstm
        self.model = self._build_tabular_model()
        self.feature_cols: list[str] = []
        self.fitted = False

    def _build_tabular_model(self):
        if importlib.util.find_spec("xgboost") is not None:
            from xgboost import XGBClassifier

            base = XGBClassifier(
                n_estimators=220,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="binary:logistic",
                eval_metric="logloss",
            )
        elif importlib.util.find_spec("lightgbm") is not None:
            from lightgbm import LGBMClassifier

            base = LGBMClassifier(
                n_estimators=260,
                learning_rate=0.04,
                num_leaves=31,
                objective="binary",
            )
        else:
            base = RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42)
        return CalibratedClassifierCV(base, cv=3, method="sigmoid")

    def fit(self, features: pd.DataFrame) -> None:
        df = features.dropna().copy()
        if len(df) < 200:
            return
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
        df = df.dropna()
        ignore = {"timestamp", "asset", "timeframe", "target", "direction"}
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
        return Prediction(up, down, self.model.__class__.__name__)
