from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None

try:
    from xgboost import XGBClassifier  # type: ignore
except Exception:  # pragma: no cover
    XGBClassifier = None


class LSTMClassifierTorch:
    """Optional lightweight LSTM classifier for sequential features."""

    def __init__(self, input_dim: int, hidden_dim: int = 32, layers: int = 1, n_classes: int = 3):
        if torch is None or nn is None:
            raise RuntimeError("PyTorch not installed")

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(input_size=input_dim, hidden_size=hidden_dim, num_layers=layers, batch_first=True)
                self.fc = nn.Linear(hidden_dim, n_classes)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])

        self.net = _Net()


class TreeDirectionModel:
    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.model = self._init_model()

    def _init_model(self):
        if XGBClassifier is not None:
            return XGBClassifier(
                n_estimators=250,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="mlogloss",
            )
        return GradientBoostingClassifier(random_state=42)

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        x_scaled = self.scaler.fit_transform(x)
        self.model.fit(x_scaled, y)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        x_scaled = self.scaler.transform(x)
        return self.model.predict_proba(x_scaled)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"scaler": self.scaler, "model": self.model}, path)

    @classmethod
    def load(cls, path: Path) -> "TreeDirectionModel":
        payload = joblib.load(path)
        obj = cls()
        obj.scaler = payload["scaler"]
        obj.model = payload["model"]
        return obj


class EnsembleSignalModel:
    """Weighted ensemble wrapper.

    Label mapping:
      0 -> BEARISH
      1 -> NEUTRAL
      2 -> BULLISH
    """

    def __init__(self, tree_model: Optional[TreeDirectionModel] = None, tree_weight: float = 1.0) -> None:
        self.tree_model = tree_model or TreeDirectionModel()
        self.tree_weight = tree_weight

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.tree_model.fit(x, y)

    def predict(self, x: np.ndarray) -> tuple[str, float, int]:
        p_tree = self.tree_model.predict_proba(x)
        probs = p_tree * self.tree_weight
        probs = probs / np.sum(probs, axis=1, keepdims=True)

        cls = int(np.argmax(probs[0]))
        conf = float(probs[0, cls])
        label = {0: "BEARISH", 1: "NEUTRAL", 2: "BULLISH"}[cls]
        return label, conf, cls

    def save(self, model_dir: Path) -> None:
        model_dir.mkdir(parents=True, exist_ok=True)
        self.tree_model.save(model_dir / "tree_model.joblib")

    @classmethod
    def load(cls, model_dir: Path) -> "EnsembleSignalModel":
        tree_path = model_dir / "tree_model.joblib"
        tree = TreeDirectionModel.load(tree_path)
        return cls(tree_model=tree)
