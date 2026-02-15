from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import signal
import threading
import time

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from data_capture.browser_engine import QuotexBrowserEngine
from data_processing.candle_reconstructor import CandleBuffer
from execution.trade_executor import TradeExecutor
from gui.main_window import MainWindow
from indicators.technical import compute_all
from ml_model.hybrid_model import HybridMLModel, Prediction
from strategy.signal_generator import SignalGenerator
from utils.config import AppConfig
from utils.logger import append_csv


class TradingOrchestrator(QObject):
    prediction_ready = pyqtSignal(object, object, str)

    def __init__(self, app: QApplication, config: AppConfig) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        self.browser = QuotexBrowserEngine(
            quotex_url=config.runtime.quotex_url,
            profile_path=config.runtime.browser_profile_path,
            cache_path=config.runtime.browser_cache_path,
            user_agent=config.runtime.browser_user_agent,
            injection_delay_ms=int(config.runtime.hook_injection_delay_seconds * 1000),
        )
        self.window = MainWindow(self.browser.view)
        self.candles = CandleBuffer(maxlen=config.runtime.history_size)
        self.model = HybridMLModel()
        self.strategy = SignalGenerator()
        self.executor = TradeExecutor(config.risk)

        self.packet_queue: queue.Queue[dict] = queue.Queue(maxsize=2000)
        self.executor_pool = ThreadPoolExecutor(max_workers=2)
        self.ml_lock = threading.Lock()
        self.first_candle_logged = False

        self.browser.bridge.packet_received.connect(self._on_packet)
        self.prediction_ready.connect(self._apply_prediction_gui)
        self.browser.page_loaded.connect(self._on_page_loaded)
        self.browser.hook_installed.connect(self._on_hook_status)
        self.window.panel.force_predict_btn.clicked.connect(self._force_predict)

        self.watchdog = QTimer()
        self.watchdog.timeout.connect(self._watchdog)
        self.watchdog.start(3000)

        self.prediction_probe = QTimer()
        self.prediction_probe.timeout.connect(self._manual_prediction_probe)
        self.prediction_probe.start(max(1, self.config.runtime.test_prediction_interval_seconds) * 1000)

        self.last_packet_ts = time.time()
        self.has_seen_market_packets = False
        self.hook_active = False
        self.watchdog_miss_count = 0

        self.logger.info("[THREADING] SUCCESS worker_pool_started max_workers=2")

    def _stage_success(self, stage: str) -> None:
        msg = f"[{stage}] SUCCESS"
        self.logger.info(msg)
        print(msg)

    def start(self) -> None:
        self.window.show()
        self.window.activateWindow()
        self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(50, lambda: self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason))
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, *_args) -> None:
        self.shutdown()

    def _on_page_loaded(self) -> None:
        self.logger.info("Quotex page loaded; waiting for delayed hook install")
        self.window.activateWindow()
        self.browser.view.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _on_hook_status(self, active: bool) -> None:
        self.hook_active = active
        self.logger.info("WebSocket hook active=%s", active)

    def _on_packet(self, packet: dict) -> None:
        packet_type = str(packet.get("type", ""))
        if packet_type.startswith("ws_"):
            self.last_packet_ts = time.time()
            self.has_seen_market_packets = True
            self._stage_success("WEBSOCKET_DATA_RECEIVE")
        if self.packet_queue.full():
            _ = self.packet_queue.get_nowait()
        self.packet_queue.put_nowait(packet)
        self.executor_pool.submit(self._process_latest_packet)

    def _force_predict(self) -> None:
        self.logger.info("Force Predict clicked")
        self.executor_pool.submit(self._run_prediction_pipeline, "force", True)

    def _manual_prediction_probe(self) -> None:
        try:
            self.logger.info("[TEST_PREDICTION_LOOP] SUCCESS timer_tick")
            self._run_prediction_pipeline(source="timer", ignore_minimum=False)
        except Exception as exc:
            self.logger.exception("AI ERROR in manual probe: %s", exc)
            print(f"AI ERROR: {exc}")

    def _process_latest_packet(self) -> None:
        try:
            self._run_prediction_pipeline(source="packet", ignore_minimum=False)
        except Exception as exc:
            self.logger.exception("AI ERROR in packet pipeline: %s", exc)
            print(f"AI ERROR: {exc}")

    def _run_prediction_pipeline(self, source: str, ignore_minimum: bool = False) -> None:
        if source == "packet":
            try:
                packet = self.packet_queue.get_nowait()
            except queue.Empty:
                return

            candle = self.candles.push_from_packet(packet)
            if candle is None:
                return
            if not self.first_candle_logged:
                self.first_candle_logged = True
                print(f"First candle: {candle.__dict__}")
                self.logger.info("First candle: %s", candle.__dict__)
            self._stage_success("CANDLE_PARSED")

        buffer_len = len(self.candles.buffer)
        self.logger.info("Candle buffer length: %s", buffer_len)
        print(f"Candle buffer length: {buffer_len}")

        min_required = min(self.config.runtime.min_candles_for_prediction, 10)
        if (not ignore_minimum) and buffer_len < min_required:
            self.window.panel.set_status("Collecting data...")
            self.logger.info("Collecting data: %s/%s candles", buffer_len, min_required)
            return

        if buffer_len == 0:
            self.window.panel.set_status("No candles yet")
            return

        df = self.candles.as_dataframe()
        features = compute_all(df)
        self._stage_success("INDICATORS_CALCULATED")

        latest_feature = features.tail(1).to_dict(orient="records")
        self.logger.debug("Feature vector sample: %s", latest_feature[0] if latest_feature else {})
        self._stage_success("FEATURE_VECTOR_BUILT")

        with self.ml_lock:
            self._stage_success("MODEL_INFERENCE_CALLED")
            if self.config.runtime.force_test_prediction_output:
                prediction = Prediction(prob_up=65.0, prob_down=35.0, model_name="ForcedTestOutput")
            else:
                self.model.fit(features.tail(1200))
                prediction = self.model.predict(features)

        self._stage_success("PREDICTION_RETURNED")
        self.logger.info("Prediction output: up=%.2f down=%.2f model=%s", prediction.prob_up, prediction.prob_down, prediction.model_name)

        signal_out = self.strategy.generate(features, prediction)

        append_csv(
            "predictions.csv",
            {
                "timestamp": time.time(),
                "asset": str(df.iloc[-1].get("asset", "UNKNOWN")),
                "timeframe": str(df.iloc[-1].get("timeframe", "1m")),
                "direction": signal_out.direction,
                "confidence": signal_out.confidence,
                "prob_up": prediction.prob_up,
                "prob_down": prediction.prob_down,
                "source": source,
            },
            headers=["timestamp", "asset", "timeframe", "direction", "confidence", "prob_up", "prob_down", "source"],
        )

        self.prediction_ready.emit(signal_out, prediction, source)

    @pyqtSlot(object, object, str)
    def _apply_prediction_gui(self, signal_out, prediction, source: str) -> None:
        self.window.panel.update_signal(signal_out)
        self._stage_success("GUI_UPDATED")

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
        if not self.hook_active:
            return
        if not self.has_seen_market_packets:
            return

        stale_for = time.time() - self.last_packet_ts
        if stale_for > self.config.runtime.websocket_reconnect_seconds:
            self.watchdog_miss_count += 1
            self.logger.warning("Market WS stale for %.1fs (miss %s)", stale_for, self.watchdog_miss_count)
            if self.watchdog_miss_count >= 3:
                self.logger.warning("Reloading page after repeated WS stalls")
                self.browser.reload()
                self.watchdog_miss_count = 0
                self.last_packet_ts = time.time()
                self.has_seen_market_packets = False
                self.hook_active = False
        else:
            self.watchdog_miss_count = 0

    def shutdown(self) -> None:
        self.watchdog.stop()
        self.prediction_probe.stop()
        self.executor_pool.shutdown(wait=False, cancel_futures=True)
        self.app.quit()
