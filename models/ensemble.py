from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


@dataclass
class EnsembleArtifacts:
    feature_cols: List[str]


class EnsembleModel:
    def __init__(self, tree_cfg: dict):
        self.scaler = StandardScaler()
        self.tree = RandomForestClassifier(
            n_estimators=int(tree_cfg.get("n_estimators", 500)),
            max_depth=int(tree_cfg.get("max_depth", 9)),
            min_samples_leaf=int(tree_cfg.get("min_samples_leaf", 20)),
            class_weight="balanced_subsample",
            random_state=13,
            n_jobs=-1,
        )
        self.temporal = LogisticRegression(max_iter=2000, multi_class="multinomial")
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.artifacts = EnsembleArtifacts(feature_cols=[])

    def fit(self, df: pd.DataFrame, feature_cols: list[str]):
        self.artifacts.feature_cols = feature_cols
        x = df[feature_cols].values
        y = df["label"].values

        x = self.scaler.fit_transform(x)
        self.tree.fit(x, y)
        seq = self._seq_embed(x)
        self.temporal.fit(seq, y)

        p = self._raw_probs(x)
        self.calibrator.fit(p[:, 1], (y == 1).astype(int))

    def predict_proba(self, df: pd.DataFrame):
        x = df[self.artifacts.feature_cols].values
        x = self.scaler.transform(x)
        p_raw = self._raw_probs(x)

        p_long = self.calibrator.transform(p_raw[:, 1])
        p_short = p_raw[:, 0]
        p_no = np.clip(1 - p_long - p_short, 0, 1)
        p = np.vstack([p_short, p_long, p_no]).T
        p = p / p.sum(axis=1, keepdims=True)
        uncertainty = np.std(np.vstack([p_raw[:,0], p_raw[:,1], p_raw[:,2]]), axis=0)
        return p, uncertainty

    def _raw_probs(self, x: np.ndarray) -> np.ndarray:
        p_tree = self.tree.predict_proba(x)
        seq = self._seq_embed(x)
        p_tmp = self.temporal.predict_proba(seq)
        p = 0.55 * p_tree + 0.45 * p_tmp
        return p / p.sum(axis=1, keepdims=True)

    def _seq_embed(self, x: np.ndarray, lag: int = 16) -> np.ndarray:
        n, d = x.shape
        out = np.zeros((n, d * 3), dtype=float)
        for i in range(n):
            seg = x[max(0, i-lag):i+1]
            out[i, :d] = seg[-1]
            out[i, d:2*d] = seg.mean(axis=0)
            out[i, 2*d:] = seg.std(axis=0)
        return out
