from __future__ import annotations

import asyncio
import logging
import time
import webbrowser

from data_capture.screen_capture import ScreenCapture
from data_processing.candle_reconstructor import CandleReconstructor
from execution.trade_executor import TradeExecutor
from gui.overlay import OverlayGUI
from indicators.technical import compute_all
from ml_model.hybrid_model import HybridMLModel
from strategy.signal_generator import SignalGenerator
from utils.config import AppConfig, save_config
from utils.logger import append_csv


class TradingOrchestrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.capture = ScreenCapture(region=config.runtime.region, target_fps=config.runtime.capture_fps)
        self.reconstructor = CandleReconstructor(history_size=config.runtime.history_size)
        self.model = HybridMLModel()
        self.strategy = SignalGenerator()
        self.executor = TradeExecutor(config.risk)
        self.gui = OverlayGUI()
        self.logger = logging.getLogger(self.__class__.__name__)

    def bootstrap(self) -> None:
        webbrowser.open(self.config.runtime.quotex_url)
        if self.config.runtime.region is None:
            self.logger.warning("No capture region configured; using primary monitor. Save region in config.json for better latency.")
        save_config(self.config)
        self.gui.start()

    async def run(self) -> None:
        self.bootstrap()
        async for packet in self.capture.stream():
            t0 = time.perf_counter()
            candle = self.reconstructor.reconstruct_latest(packet.frame, packet.ts)
            if candle is None:
                continue

            candles = self.reconstructor.as_dataframe()
            features = compute_all(candles)
            self.model.fit(features.tail(800))
            pred = self.model.predict(features)
            signal = self.strategy.generate(features, pred)

            append_csv(
                "predictions.csv",
                {
                    "timestamp": packet.ts,
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "ml_up": pred.prob_up,
                    "ml_down": pred.prob_down,
                    "indicator_score": signal.indicator_score,
                    "pattern_score": signal.pattern_score,
                    "latency_ms": (time.perf_counter() - t0) * 1000,
                },
                headers=["timestamp", "direction", "confidence", "ml_up", "ml_down", "indicator_score", "pattern_score", "latency_ms"],
            )

            if self.config.runtime.auto_trade_enabled:
                self.executor.execute(signal.direction, signal.confidence, self.config.runtime.min_confidence)

            self.gui.update(signal, pred)
            await asyncio.sleep(0)
