from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .indicators import add_indicators, feature_columns
from .models import EnsembleSignalModel


def build_labels(close: pd.Series, eps: float = 1e-9) -> pd.Series:
    next_close = close.shift(-1)
    diff = next_close - close
    labels = np.where(diff > eps, 2, np.where(diff < -eps, 0, 1))
    return pd.Series(labels, index=close.index)


def train(input_path: Path, model_dir: Path) -> None:
    df = pd.read_csv(input_path)
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    feat_df = add_indicators(df)
    feat_df["label"] = build_labels(feat_df["close"])
    feat_df = feat_df.dropna().copy()
    if len(feat_df) < 200:
        raise ValueError("Not enough rows after indicator warm-up. Need at least ~200.")

    x = feat_df[feature_columns()].to_numpy()
    y = feat_df["label"].astype(int).to_numpy()

    model = EnsembleSignalModel()
    model.fit(x, y)
    model.save(model_dir)

    print(f"Saved model artifacts to: {model_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ensemble signal model")
    parser.add_argument("--input", type=Path, required=True, help="Path to candles CSV")
    parser.add_argument("--model-dir", type=Path, default=Path("models"), help="Output model directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train(args.input, args.model_dir)


if __name__ == "__main__":
    main()
