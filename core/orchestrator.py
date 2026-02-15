from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import signal
import threading
import time

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication

from data_capture.browser_engine import QuotexBrowserEngine
from data_processing.candle_reconstructor import CandleBuffer
from execution.trade_executor import TradeExecutor
from gui.main_window import MainWindow
from indicators.technical import compute_all
from ml_model.hybrid_model import HybridMLModel
from strategy.signal_generator import SignalGenerator
from utils.config import AppConfig
from utils.logger import append_csv


class TradingOrchestrator(QObject):
    def __init__(self, app: QApplication, config: AppConfig) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        self.browser = QuotexBrowserEngine(config.runtime.quotex_url)
        self.window = MainWindow(self.browser.view)
        self.candles = CandleBuffer(maxlen=config.runtime.history_size)
        self.model = HybridMLModel()
        self.strategy = SignalGenerator()
        self.executor = TradeExecutor(config.risk)

        self.packet_queue: queue.Queue[dict] = queue.Queue(maxsize=2000)
        self.executor_pool = ThreadPoolExecutor(max_workers=2)
        self.ml_lock = threading.Lock()

        self.browser.bridge.packet_received.connect(self._on_packet)
        self.browser.page_loaded.connect(self._on_page_loaded)

        self.watchdog = QTimer()
        self.watchdog.timeout.connect(self._watchdog)
        self.watchdog.start(3000)
        self.last_packet_ts = time.time()

    def start(self) -> None:
        self.window.show()
        self.window.activateWindow()
        self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(50, lambda: self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason))
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, *_args) -> None:
        self.shutdown()

    def _on_page_loaded(self) -> None:
        self.logger.info("Quotex page loaded; websocket hooks armed")
        self.window.activateWindow()
        self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _on_packet(self, packet: dict) -> None:
        self.last_packet_ts = time.time()
        if self.packet_queue.full():
            _ = self.packet_queue.get_nowait()
        self.packet_queue.put_nowait(packet)
        self.executor_pool.submit(self._process_latest_packet)

    def _process_latest_packet(self) -> None:
        try:
            packet = self.packet_queue.get_nowait()
        except queue.Empty:
            return

        candle = self.candles.push_from_packet(packet)
        if candle is None:
            return

        df = self.candles.as_dataframe()
        features = compute_all(df)

        with self.ml_lock:
            self.model.fit(features.tail(1200))
            prediction = self.model.predict(features)
        signal_out = self.strategy.generate(features, prediction)

        append_csv(
            "predictions.csv",
            {
                "timestamp": candle.timestamp,
                "asset": candle.asset,
                "timeframe": candle.timeframe,
                "direction": signal_out.direction,
                "confidence": signal_out.confidence,
                "prob_up": prediction.prob_up,
                "prob_down": prediction.prob_down,
            },
            headers=["timestamp", "asset", "timeframe", "direction", "confidence", "prob_up", "prob_down"],
        )

        self.window.panel.update_signal(signal_out)

        auto_enabled = self.window.panel.auto_toggle.isChecked() or self.config.runtime.auto_trade_enabled
        threshold = float(self.window.panel.threshold_slider.value())
        if auto_enabled:
            decision = self.executor.execute(
                signal_out.direction,
                signal_out.confidence,
                threshold,
                self.browser.evaluate_js,
            )
            self.window.panel.add_trade(signal_out.direction, signal_out.confidence, decision.reason)

    def _watchdog(self) -> None:
        if time.time() - self.last_packet_ts > self.config.runtime.websocket_reconnect_seconds:
            self.logger.warning("No WebSocket packets observed; reloading page")
            self.browser.reload()
            self.last_packet_ts = time.time()

    def shutdown(self) -> None:
        self.watchdog.stop()
        self.executor_pool.shutdown(wait=False, cancel_futures=True)
        self.app.quit()
