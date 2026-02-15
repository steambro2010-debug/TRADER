import queue
import signal
import threading
import time
from datetime import datetime

import psutil

from ai.model_loader import ModelLoader
from ai.predictor import Predictor
from browser.browser_launcher import BrowserLauncher
from data.buffer import CandleBuffer
from data.indicators import compute_indicators
from gui.dashboard import Dashboard
from utils.config import ConfigManager
from utils.logger import setup_logger
from vision.candle_detector import CandleDetector
from vision.candle_tracker import CandleTracker
from vision.screen_capture import Region, RegionSelector, ScreenCaptureEngine


class AppController:
    def __init__(self) -> None:
        self.logger = setup_logger()
        self.config = ConfigManager()
        self.stop_event = threading.Event()

        self.state = {
            "metrics": {"cpu": 0, "fps": 0, "buffer_size": 0},
            "prediction": None,
            "trade_log": [],
            "ai_status": "initializing",
        }

        self.frame_queue: queue.Queue = queue.Queue(maxsize=5)
        self.signal_queue: queue.Queue = queue.Queue(maxsize=20)
        self.candle_buffer = CandleBuffer(capacity=2000)

        self.browser = BrowserLauncher(self.logger)
        self.capture_engine = None
        self.tracker = None
        self.ai_thread = None
        self.metric_thread = None

    def run(self) -> None:
        self._setup_signals()
        cfg = self.config.all()

        session = self.browser.launch(cfg["quotex_url"], self.stop_event)
        if session is None:
            self.state["ai_status"] = "browser failed"

        region_data = self.config.get("region")
        if not region_data:
            self.logger.info("No region found, opening one-time region selector.")
            selected = RegionSelector(self.logger).select()
            if not selected:
                raise RuntimeError("Region selection is required for first run.")
            self.config.set("region", selected.__dict__)
            region_data = selected.__dict__
            self.logger.info("Region saved permanently to config.json")

        region = Region(**region_data)
        self.capture_engine = ScreenCaptureEngine(
            region=region,
            fps_cap=int(cfg["fps_cap"]),
            frame_queue=self.frame_queue,
            metrics=self.state["metrics"],
            logger=self.logger,
        )

        detector = CandleDetector(shift_threshold=float(cfg["x_shift_threshold"]), logger=self.logger)
        self.tracker = CandleTracker(
            frame_queue=self.frame_queue,
            signal_queue=self.signal_queue,
            candle_buffer=self.candle_buffer,
            detector=detector,
            candle_duration_sec=int(cfg["candle_duration_sec"]),
            metrics=self.state["metrics"],
            logger=self.logger,
        )

        model = ModelLoader(cfg["model_path"], self.logger).load()
        predictor = Predictor(model, self.logger)

        self.capture_engine.start()
        self.tracker.start()
        self.ai_thread = threading.Thread(target=self._ai_loop, args=(predictor,), name="ai-thread", daemon=True)
        self.ai_thread.start()
        self.metric_thread = threading.Thread(target=self._metric_loop, name="metrics-thread", daemon=True)
        self.metric_thread.start()

        dashboard = Dashboard(self.state, self.shutdown, self.logger)
        self.state["ai_status"] = "running"
        dashboard.run()

    def _ai_loop(self, predictor: Predictor) -> None:
        cfg = self.config.all()
        min_candles = int(cfg["min_candles_required"])
        interval = int(cfg["prediction_interval"])
        confidence_threshold = float(cfg["confidence_threshold"])
        last_prediction = 0.0

        while not self.stop_event.is_set():
            now = time.time()
            triggered = False
            try:
                self.signal_queue.get(timeout=0.6)
                triggered = True
            except queue.Empty:
                pass

            if not triggered and now - last_prediction < interval:
                continue

            candles = self.candle_buffer.all()
            if len(candles) < min_candles:
                self.state["ai_status"] = f"collecting data ({len(candles)}/{min_candles})"
                continue

            closes = [c.close for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            indicators = compute_indicators(closes, highs, lows)
            prediction = predictor.predict(indicators)

            self.state["prediction"] = prediction
            self.state["ai_status"] = "running"
            last_prediction = now

            if prediction.confidence >= confidence_threshold:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.state["trade_log"].append(
                    f"{timestamp} | {prediction.direction:<4} | {prediction.confidence * 100:6.2f}% | pending"
                )

    def _metric_loop(self) -> None:
        while not self.stop_event.is_set():
            self.state["metrics"]["cpu"] = round(psutil.cpu_percent(interval=1), 1)

    def _setup_signals(self) -> None:
        def _handle_signal(*_):
            self.shutdown()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def shutdown(self) -> None:
        if self.stop_event.is_set():
            return
        self.logger.info("Graceful shutdown initiated...")
        self.stop_event.set()
        if self.capture_engine:
            self.capture_engine.stop()
        if self.tracker:
            self.tracker.stop()
        if self.browser:
            self.browser.close()
