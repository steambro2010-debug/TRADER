from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Optional

import pandas as pd

from .backtest import RollingAccuracy
from .candle_extractor import Candle, CandleExtractor
from .capture import ScreenCapture
from .config import AppConfig
from .data import DataLogger
from .indicators import add_indicators, feature_columns
from .models import EnsembleSignalModel


@dataclass
class LiveState:
    last_candle: Optional[Candle] = None
    last_signal: str = "N/A"
    last_confidence: float = 0.0
    prediction_enabled: bool = True
    rolling_accuracy: float = 0.0


class RealtimePipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.capture = ScreenCapture(
            monitor_index=config.capture.monitor_index,
            fps_target=config.capture.fps_target,
        )
        self.extractor = CandleExtractor(config.extractor)
        self.logger = DataLogger(config.pipeline.log_dir)
        self.model = self._load_or_bootstrap_model()
        self.accuracy = RollingAccuracy(window=config.pipeline.rolling_accuracy_window)
        self.state = LiveState(prediction_enabled=config.pipeline.prediction_enabled)

        self._frames: Queue = Queue(maxsize=5)
        self._stop = threading.Event()
        self._candles_df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close"])
        self._last_pred_class: Optional[int] = None
        self._last_pred_close: Optional[float] = None

    def _load_or_bootstrap_model(self) -> EnsembleSignalModel:
        try:
            return EnsembleSignalModel.load(self.config.pipeline.models_dir)
        except Exception:
            return EnsembleSignalModel()

    def start(self) -> None:
        region = self.config.capture.selected_region or self.capture.select_region()
        t1 = threading.Thread(target=self._capture_loop, args=(region,), daemon=True)
        t2 = threading.Thread(target=self._process_loop, daemon=True)
        t1.start()
        t2.start()

    def stop(self) -> None:
        self._stop.set()

    def toggle_predictions(self) -> None:
        self.state.prediction_enabled = not self.state.prediction_enabled

    def _capture_loop(self, region: tuple[int, int, int, int]) -> None:
        for packet in self.capture.stream(region):
            if self._stop.is_set():
                break
            try:
                self._frames.put(packet, timeout=0.05)
            except Exception:
                pass

    def _process_loop(self) -> None:
        while not self._stop.is_set():
            try:
                packet = self._frames.get(timeout=0.5)
            except Empty:
                continue

            candles = self.extractor.extract_candles(packet.frame_bgr, packet.timestamp)
            if not candles:
                continue

            latest = candles[-1]
            self.state.last_candle = latest
            self.logger.append_candle(latest)
            self._ingest_candle(latest)

    def _ingest_candle(self, candle: Candle) -> None:
        new_row = pd.DataFrame(
            [{"timestamp": candle.timestamp, "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close}]
        )
        self._candles_df = pd.concat([self._candles_df, new_row], ignore_index=True).tail(1000)

        if len(self._candles_df) < self.config.pipeline.min_candles_for_features:
            return

        if self._last_pred_class is not None and self._last_pred_close is not None:
            actual = 2 if candle.close > self._last_pred_close else 0 if candle.close < self._last_pred_close else 1
            self.accuracy.add(predicted=self._last_pred_class, actual=actual)
            self.state.rolling_accuracy = self.accuracy.value

        if not self.state.prediction_enabled:
            return

        feat_df = add_indicators(self._candles_df).dropna()
        if feat_df.empty:
            return
        x = feat_df[feature_columns()].tail(1).to_numpy()
        signal, confidence, pred_class = self.model.predict(x)

        self.state.last_signal = signal
        self.state.last_confidence = confidence

        self.logger.append_signal(
            {
                "timestamp": time.time(),
                "signal": signal,
                "confidence": confidence,
                "pred_class": pred_class,
                "close_at_prediction": candle.close,
                "rolling_accuracy": self.state.rolling_accuracy,
            }
        )

        self._last_pred_class = pred_class
        self._last_pred_close = candle.close
