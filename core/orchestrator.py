from __future__ import annotations

import logging
import queue
import signal
import threading
import time

import cv2
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from core.ai_engine import AIEngine
from data_capture.capture import ScreenRegionCapture
from data_capture.candle_tracker import CandleTracker
from data_capture.data_buffer import RollingOHLCBuffer
from data_capture.vision import CandleVisionProcessor
from execution.trade_executor import TradeExecutor
from gui.main_window import MainWindow
from utils.config import AppConfig, save_config
from utils.logger import append_csv


class TradingOrchestrator(QObject):
    ui_update = pyqtSignal(dict)

    def __init__(self, app: QApplication, config: AppConfig) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        self.window = MainWindow(None)
        self.capture = ScreenRegionCapture(config.runtime.capture_region, config.runtime.capture_fps)
        self.vision = CandleVisionProcessor(debug=config.runtime.debug_vision)
        self.tracker = CandleTracker(60)
        self.buffer = RollingOHLCBuffer(maxlen=config.runtime.history_size)
        self.ai = AIEngine(
            predict_interval_seconds=config.runtime.test_prediction_interval_seconds,
            min_candles=config.runtime.min_candles_for_prediction,
        )
        self.executor = TradeExecutor(config.risk)

        self.frame_queue: queue.Queue[tuple] = queue.Queue(maxsize=8)
        self.running = False
        self.worker: threading.Thread | None = None
        self.last_predict_ts = time.time()

        self.ui_update.connect(self._apply_ui)
        self.window.panel.force_predict_btn.clicked.connect(self._force_predict)

    def start(self) -> None:
        self.window.show()

        if self.capture.region is None:
            region = self.capture.select_region_once()
            self.config.runtime.capture_region = region
            save_config(self.config)

        self.running = True
        self.worker = threading.Thread(target=self._process_loop, daemon=True)
        self.worker.start()
        self.capture.start(self._on_frame)

        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, *_args) -> None:
        self.shutdown()

    def _on_frame(self, frame, ts: float) -> None:
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
        self.frame_queue.put_nowait((frame, ts))

    def _force_predict(self) -> None:
        df = self.buffer.to_df()
        payload, status = self.ai.maybe_predict(df, new_candle_closed=True, force=True)
        self.ui_update.emit(self._pack_ui(payload, status, latency_ms=0.0))

    def _pack_ui(self, payload, status: str, latency_ms: float) -> dict:
        cpu = 0.0
        try:
            import psutil  # type: ignore

            cpu = float(psutil.cpu_percent(interval=None))
        except Exception:
            pass

        now = time.time()
        fps = 1.0 / max(now - self.last_predict_ts, 1e-6)
        self.last_predict_ts = now

        base = {
            "status": status,
            "buffer_len": len(self.buffer),
            "cpu": cpu,
            "fps": fps,
            "latency_ms": latency_ms,
        }
        if payload:
            base.update(payload)
        return base

    def _process_loop(self) -> None:
        while self.running:
            try:
                frame, ts = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            candidates, dbg, ms = self.vision.detect(frame)
            closed, current = self.tracker.update(candidates, ts, frame.shape[0])

            if self.config.runtime.debug_vision:
                overlay = dbg.copy()
                cv2.putText(overlay, f"candles={len(self.buffer)} proc={ms:.1f}ms", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 180), 1)
                cv2.imshow("Vision Debug", overlay)
                cv2.waitKey(1)

            new_closed = False
            if closed is not None:
                if self.buffer.append(closed):
                    new_closed = True
                    append_csv(
                        "candles.csv",
                        {
                            "timestamp": closed.timestamp,
                            "open": closed.open,
                            "high": closed.high,
                            "low": closed.low,
                            "close": closed.close,
                            "volume": closed.volume,
                        },
                        headers=["timestamp", "open", "high", "low", "close", "volume"],
                    )

            df = self.buffer.to_df()
            payload, status = self.ai.maybe_predict(df, new_candle_closed=new_closed, force=False)
            ui = self._pack_ui(payload, status if status != "Collecting" else f"Collecting data: {len(self.buffer)} / {self.ai.min_candles} candles", ms)
            self.ui_update.emit(ui)

    @pyqtSlot(dict)
    def _apply_ui(self, payload: dict) -> None:
        self.window.panel.set_metrics(
            float(payload.get("cpu", 0.0)),
            float(payload.get("fps", 0.0)),
            float(payload.get("latency_ms", 0.0)),
            int(payload.get("buffer_len", 0)),
        )
        self.window.panel.set_status(str(payload.get("status", "Collecting")))

        if "direction" in payload:
            self.window.panel.update_dashboard(
                direction=str(payload.get("direction", "-")),
                confidence=float(payload.get("confidence", 0.0)),
                prob_up=float(payload.get("prob_up", 0.0)),
                prob_down=float(payload.get("prob_down", 0.0)),
                model_mode=str(payload.get("model_mode", "Hybrid")),
                indicators=dict(payload.get("indicators", {})),
            )

            if self.window.panel.auto_toggle.isChecked() or self.config.runtime.auto_trade_enabled:
                decision = self.executor.execute(
                    str(payload.get("direction", "UP")),
                    float(payload.get("confidence", 0.0)),
                    float(self.window.panel.threshold_slider.value()),
                    lambda _script: None,
                )
                self.window.panel.add_trade(str(payload.get("direction", "UP")), float(payload.get("confidence", 0.0)), decision.reason)

    def shutdown(self) -> None:
        self.running = False
        self.capture.stop()
        if self.config.runtime.debug_vision:
            cv2.destroyAllWindows()
        self.app.quit()
