from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


EXPECTED_CLASSES = np.array([0, 1, 2], dtype=int)


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
        self.temporal = LogisticRegression(max_iter=2000, multi_class="multinomial", class_weight="balanced")
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.artifacts = EnsembleArtifacts(feature_cols=[])

    def fit(self, df: pd.DataFrame, feature_cols: list[str]):
        self.artifacts.feature_cols = feature_cols
        x = df[feature_cols].values
        y = df["label"].astype(int).values

        uniq = np.sort(np.unique(y))
        if len(uniq) < 3:
            counts = df["label"].value_counts().to_dict()
            raise ValueError(
                "Strict 3-class training failed: expected labels {0,1,2} but got "
                f"{uniq.tolist()} with counts={counts}. "
                "Adjust triple-barrier/neutral label params to produce no-trade samples."
            )

        x = self.scaler.fit_transform(x)
        self.tree.fit(x, y)
        seq = self._seq_embed(x)
        self.temporal.fit(seq, y)

        p = self._raw_probs(x)
        assert p.shape[1] == 3, f"Internal probability matrix must be 3-wide, got {p.shape}"
        self.calibrator.fit(p[:, 1], (y == 1).astype(int))

    def predict_proba(self, df: pd.DataFrame):
        x = df[self.artifacts.feature_cols].values
        x = self.scaler.transform(x)
        p_raw = self._raw_probs(x)

        if p_raw.shape[1] != 3:
            raise ValueError(f"predict_proba expected 3 classes [short,long,no-trade], got shape={p_raw.shape}")

        p_long = self.calibrator.transform(p_raw[:, 1])
        p_short = p_raw[:, 0]
        p_no = np.clip(1 - p_long - p_short, 0, 1)

        p = np.vstack([p_short, p_long, p_no]).T
        p = p / p.sum(axis=1, keepdims=True)

        assert p.shape[1] == 3, f"Output probability matrix must be (N,3), got {p.shape}"
        uncertainty = np.std(p_raw, axis=1)
        return p, uncertainty

    def _raw_probs(self, x: np.ndarray) -> np.ndarray:
        p_tree = self._aligned_proba(self.tree.predict_proba(x), self.tree.classes_)
        seq = self._seq_embed(x)
        p_tmp = self._aligned_proba(self.temporal.predict_proba(seq), self.temporal.classes_)

        p = 0.55 * p_tree + 0.45 * p_tmp
        p = p / p.sum(axis=1, keepdims=True)
        return p

    @staticmethod
    def _aligned_proba(probs: np.ndarray, classes: np.ndarray) -> np.ndarray:
        """Align model probabilities into fixed class order [0,1,2].

        Handles 2-class edge case defensively, but strict training should prevent it.
        """
        aligned = np.zeros((probs.shape[0], 3), dtype=float)
        idx = {int(c): i for i, c in enumerate(classes)}
        for cls in [0, 1, 2]:
            if cls in idx:
                aligned[:, cls] = probs[:, idx[cls]]

        row_sum = aligned.sum(axis=1, keepdims=True)
        missing_rows = row_sum.squeeze() == 0
        if np.any(missing_rows):
            aligned[missing_rows, 2] = 1.0
            row_sum = aligned.sum(axis=1, keepdims=True)

        aligned = aligned / np.clip(row_sum, 1e-9, None)
        return aligned

    def _seq_embed(self, x: np.ndarray, lag: int = 16) -> np.ndarray:
        n, d = x.shape
        out = np.zeros((n, d * 3), dtype=float)
        for i in range(n):
            seg = x[max(0, i - lag) : i + 1]
            out[i, :d] = seg[-1]
            out[i, d : 2 * d] = seg.mean(axis=0)
            out[i, 2 * d :] = seg.std(axis=0)
        return out
