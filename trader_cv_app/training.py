from __future__ import annotations

from pathlib import Path
from typing import Tuple

import joblib
import numpy as np
import pandas as pd


def save_ohlc_csv(df: pd.DataFrame, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_header = not Path(path).exists()
    df.to_csv(path, mode="a", header=write_header, index=False)


def train_offline_models(feature_df: pd.DataFrame, model_dir: str, sequence_length: int = 20) -> Tuple[bool, str]:
    if feature_df.empty or "target" not in feature_df.columns:
        return False, "No training data available."

    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    cols = [c for c in feature_df.columns if c not in {"timestamp", "target"}]
    X = feature_df[cols]
    y = feature_df["target"].astype(int)

    try:
        from sklearn.ensemble import RandomForestClassifier

        rf = RandomForestClassifier(n_estimators=200, random_state=42)
        rf.fit(X, y)
        joblib.dump(rf, model_path / "rf.joblib")
    except Exception as exc:
        return False, f"RandomForest training failed: {exc}"

    try:
        from xgboost import XGBClassifier

        xgb = XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
        )
        xgb.fit(X, y)
        joblib.dump(xgb, model_path / "xgb.joblib")
    except Exception:
        pass

    try:
        from tensorflow import keras

        if len(feature_df) > sequence_length + 30:
            X_seq, y_seq = _make_sequences(X.to_numpy(), y.to_numpy(), sequence_length)
            model = keras.Sequential(
                [
                    keras.layers.Input(shape=(sequence_length, X.shape[1])),
                    keras.layers.LSTM(32),
                    keras.layers.Dense(16, activation="relu"),
                    keras.layers.Dense(1, activation="sigmoid"),
                ]
            )
            model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            model.fit(X_seq, y_seq, epochs=5, batch_size=32, verbose=0)
            model.save(model_path / "lstm.keras")
    except Exception:
        pass

    return True, f"Models trained and stored in {model_dir}"


def _make_sequences(X: np.ndarray, y: np.ndarray, seq_len: int):
    Xs, ys = [], []
    for i in range(seq_len, len(X)):
        Xs.append(X[i - seq_len : i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)
