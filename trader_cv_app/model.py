from __future__ import annotations

import logging
import threading
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .data_models import ModelStatus, PredictionResult

logger = logging.getLogger(__name__)


class EnsembleModel:
    def __init__(self, model_dir: Path, sequence_length: int = 20):
        self.model_dir = Path(model_dir)
        self.sequence_length = sequence_length
        self.rf = None
        self.xgb = None
        self.lstm = None
        self.status = ModelStatus.UNTRAINED
        self.message = "No trained model loaded"
        self.weights = {"rf": 0.35, "xgb": 0.35, "lstm": 0.30}

    def load(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        rf_path = self.model_dir / "rf.joblib"
        xgb_path = self.model_dir / "xgb.joblib"
        lstm_path = self.model_dir / "lstm.keras"

        loaded_any = False
        if rf_path.exists():
            self.rf = joblib.load(rf_path)
            loaded_any = True
        if xgb_path.exists():
            self.xgb = joblib.load(xgb_path)
            loaded_any = True
        if lstm_path.exists():
            try:
                from tensorflow import keras

                self.lstm = keras.models.load_model(lstm_path)
                loaded_any = True
            except Exception as exc:
                logger.warning("LSTM load failed: %s", exc)

        self.status = ModelStatus.READY if loaded_any else ModelStatus.UNTRAINED
        self.message = "Model ready" if loaded_any else "No trained model files found"

    def predict(self, feature_df: pd.DataFrame) -> PredictionResult | None:
        if self.status != ModelStatus.READY or feature_df.empty:
            return None

        cols = [c for c in feature_df.columns if c not in {"timestamp", "target"}]
        row = feature_df[cols].iloc[[-1]]
        probs = {
            "rf": self._predict_tree(self.rf, row),
            "xgb": self._predict_tree(self.xgb, row),
            "lstm": self._predict_lstm(feature_df[cols]),
        }

        bullish = sum(self.weights[k] * probs[k] for k in probs)
        bearish = 1.0 - bullish
        agreement = 1.0 - float(np.std(list(probs.values())))
        confidence = float(np.clip(agreement, 0.0, 1.0))

        return PredictionResult(
            bullish_probability=float(np.clip(bullish, 0, 1)),
            bearish_probability=float(np.clip(bearish, 0, 1)),
            confidence=confidence,
            model_breakdown=probs,
        )

    @staticmethod
    def _predict_tree(model, row: pd.DataFrame) -> float:
        if model is None:
            return 0.5
        if hasattr(model, "predict_proba"):
            return float(model.predict_proba(row)[0][1])
        return float(model.predict(row)[0])

    def _predict_lstm(self, df: pd.DataFrame) -> float:
        if self.lstm is None or len(df) < self.sequence_length:
            return 0.5
        seq = df.tail(self.sequence_length).to_numpy().reshape(1, self.sequence_length, df.shape[1])
        pred = self.lstm.predict(seq, verbose=0)
        return float(pred[0][0])

    def train_from_csv(self, csv_path: Path) -> tuple[bool, str]:
        try:
            self.status = ModelStatus.TRAINING
            self.message = "Training in progress..."
            df = pd.read_csv(csv_path)
            if df.empty or "target" not in df.columns:
                self.status = ModelStatus.ERROR
                self.message = "Training data missing target"
                return False, self.message

            X = df[[c for c in df.columns if c not in {"timestamp", "target"}]]
            y = df["target"].astype(int)

            from sklearn.ensemble import RandomForestClassifier

            rf = RandomForestClassifier(n_estimators=250, random_state=42, n_jobs=-1)
            rf.fit(X, y)
            joblib.dump(rf, self.model_dir / "rf.joblib")

            try:
                from xgboost import XGBClassifier

                xgb = XGBClassifier(
                    n_estimators=300,
                    learning_rate=0.03,
                    max_depth=5,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    eval_metric="logloss",
                    tree_method="hist",
                )
                xgb.fit(X, y)
                joblib.dump(xgb, self.model_dir / "xgb.joblib")
            except Exception as exc:
                logger.warning("XGBoost train skipped: %s", exc)

            try:
                from tensorflow import keras

                if len(X) > self.sequence_length + 32:
                    X_seq, y_seq = self._make_seq(X.to_numpy(), y.to_numpy())
                    lstm = keras.Sequential(
                        [
                            keras.layers.Input(shape=(self.sequence_length, X.shape[1])),
                            keras.layers.LSTM(48),
                            keras.layers.Dense(16, activation="relu"),
                            keras.layers.Dense(1, activation="sigmoid"),
                        ]
                    )
                    lstm.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
                    lstm.fit(X_seq, y_seq, epochs=8, batch_size=64, verbose=0)
                    lstm.save(self.model_dir / "lstm.keras")
            except Exception as exc:
                logger.warning("LSTM train skipped: %s", exc)

            self.load()
            return True, "Training complete"
        except Exception as exc:
            self.status = ModelStatus.ERROR
            self.message = f"Training failed: {exc}"
            return False, self.message

    def _make_seq(self, X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs = [X[i - self.sequence_length : i] for i in range(self.sequence_length, len(X))]
        ys = [y[i] for i in range(self.sequence_length, len(y))]
        return np.asarray(xs), np.asarray(ys)


class InferenceWorker(threading.Thread):
    def __init__(self, feature_queue, prediction_queue, error_queue, ensemble: EnsembleModel):
        super().__init__(daemon=True)
        self.feature_queue = feature_queue
        self.prediction_queue = prediction_queue
        self.error_queue = error_queue
        self.ensemble = ensemble
        self._running = threading.Event()
        self._running.set()

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        while self._running.is_set():
            try:
                feature_df = self.feature_queue.get(timeout=0.5)
            except Exception:
                continue
            try:
                prediction = self.ensemble.predict(feature_df)
                if prediction is not None:
                    if self.prediction_queue.full():
                        self.prediction_queue.get_nowait()
                    self.prediction_queue.put_nowait(prediction)
            except Exception as exc:
                self.error_queue.put_nowait({"type": "model", "message": f"Inference failed: {exc}"})
