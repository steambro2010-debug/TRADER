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
    prediction_ready = pyqtSignal(dict)

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

        self.total_packets = 0
        self.market_packets = 0
        self.parsed_candles = 0

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
        self.last_predict_ts = time.time()
        self.has_seen_market_packets = False
        self.hook_active = False
        self.watchdog_miss_count = 0

        self.logger.info("[THREADING] SUCCESS worker_pool_started max_workers=2")

    def _cpu_percent(self) -> float:
        try:
            import psutil  # type: ignore

            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return 0.0

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
        self.total_packets += 1
        packet_type = str(packet.get("type", ""))
        if packet_type.startswith("ws_"):
            self.last_packet_ts = time.time()
            self.has_seen_market_packets = True
            self._stage_success("WEBSOCKET_DATA_RECEIVE")

        if packet_type in {"ws_message", "ws_raw"}:
            self.market_packets += 1
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
            self.executor_pool.submit(self._run_prediction_pipeline, "timer", False)
        except Exception as exc:
            self.logger.exception("AI ERROR in manual probe: %s", exc)
            print(f"AI ERROR: {exc}")

    def _process_latest_packet(self) -> None:
        try:
            self._run_prediction_pipeline(source="packet", ignore_minimum=False)
        except Exception as exc:
            self.logger.exception("AI ERROR in packet pipeline: %s", exc)
            print(f"AI ERROR: {exc}")

    def _emit_ui_status(self, status: str, latency_ms: float) -> None:
        candles = len(self.candles.buffer)
        self.prediction_ready.emit(
            {
                "status": status,
                "buffer_len": candles,
                "cpu": self._cpu_percent(),
                "fps": 1.0 / max(time.time() - self.last_packet_ts, 1e-6),
                "latency_ms": latency_ms,
            }
        )

    def _run_prediction_pipeline(self, source: str, ignore_minimum: bool = False) -> None:
        t0 = time.perf_counter()
        if source == "packet":
            try:
                packet = self.packet_queue.get_nowait()
            except queue.Empty:
                return

            candle = self.candles.push_from_packet(packet)
            if candle is None:
                return
            self.parsed_candles += 1
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
            self._emit_ui_status(f"Collecting data: {buffer_len} / {min_required} candles", (time.perf_counter() - t0) * 1000)
            return

        if buffer_len == 0:
            self._emit_ui_status("No candles yet", (time.perf_counter() - t0) * 1000)
            return

        df = self.candles.as_dataframe()
        features = compute_all(df)
        self._stage_success("INDICATORS_CALCULATED")
        self._stage_success("FEATURE_VECTOR_BUILT")

        with self.ml_lock:
            self._stage_success("MODEL_INFERENCE_CALLED")
            trained_now = False
            if self.config.runtime.force_test_prediction_output:
                prediction = Prediction(prob_up=65.0, prob_down=35.0, model_name="ForcedTestOutput")
                trained_now = True
            else:
                trained_now = self.model.fit(features.tail(1200))
                prediction = self.model.predict(features)

        self._stage_success("PREDICTION_RETURNED")
        signal_out = self.strategy.generate(features, prediction)
        row = features.iloc[-1]
        latency_ms = (time.perf_counter() - t0) * 1000

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
                "model_trained": self.model.fitted,
            },
            headers=["timestamp", "asset", "timeframe", "direction", "confidence", "prob_up", "prob_down", "source", "model_trained"],
        )

        now = time.time()
        fps = 1.0 / max(now - self.last_predict_ts, 1e-6)
        self.last_predict_ts = now

        status = "Analyzing…"
        if not self.model.fitted and not self.config.runtime.force_test_prediction_output:
            status = "AI warming model (fallback probabilities)"
        elif trained_now or self.model.fitted:
            status = "AI Ready"

        self.prediction_ready.emit(
            {
                "status": status,
                "direction": signal_out.direction,
                "confidence": signal_out.confidence,
                "prob_up": prediction.prob_up,
                "prob_down": prediction.prob_down,
                "model_mode": prediction.model_name,
                "indicators": {
                    "rsi": float(row.get("rsi_14", 0.0)),
                    "macd_hist": float(row.get("macd_hist", 0.0)),
                    "adx": float(row.get("adx_14", 0.0)),
                    "volatility": float(row.get("volatility_10", 0.0)),
                    "trend_bias": float(signal_out.indicator_bias),
                },
                "buffer_len": buffer_len,
                "cpu": self._cpu_percent(),
                "fps": fps,
                "latency_ms": latency_ms,
                "auto_enabled": self.window.panel.auto_toggle.isChecked() or self.config.runtime.auto_trade_enabled,
                "threshold": float(self.window.panel.threshold_slider.value()),
                "feed_health": f"packets={self.total_packets} ws={self.market_packets} candles={self.parsed_candles}",
            }
        )

    @pyqtSlot(dict)
    def _apply_prediction_gui(self, payload: dict) -> None:
        self.window.panel.set_metrics(
            float(payload.get("cpu", 0.0)),
            float(payload.get("fps", 0.0)),
            float(payload.get("latency_ms", 0.0)),
            int(payload.get("buffer_len", 0)),
        )
        status = str(payload.get("status", "Analyzing…"))
        feed_health = str(payload.get("feed_health", ""))
        self.window.panel.set_status(f"{status} | {feed_health}" if feed_health else status)

        if "direction" not in payload:
            return

        self.window.panel.update_dashboard(
            direction=str(payload.get("direction", "-")),
            confidence=float(payload.get("confidence", 0.0)),
            prob_up=float(payload.get("prob_up", 0.0)),
            prob_down=float(payload.get("prob_down", 0.0)),
            model_mode=str(payload.get("model_mode", "Hybrid")),
            indicators=dict(payload.get("indicators", {})),
        )
        self._stage_success("GUI_UPDATED")

        if bool(payload.get("auto_enabled", False)):
            decision = self.executor.execute(
                str(payload.get("direction", "UP")),
                float(payload.get("confidence", 0.0)),
                float(payload.get("threshold", self.window.panel.threshold_slider.value())),
                self.browser.evaluate_js,
            )
            self.window.panel.add_trade(str(payload.get("direction", "UP")), float(payload.get("confidence", 0.0)), decision.reason)

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
