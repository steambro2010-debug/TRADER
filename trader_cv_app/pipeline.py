from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2

from .capture import FramePacket, ScreenCaptureThread
from .config import AppConfig
from .cv_processor import CandleDetector
from .data_models import SharedState
from .features import candles_to_feature_frame
from .models import EnsemblePredictor
from .training import save_ohlc_csv


@dataclass
class PipelineHandles:
    capture_thread: Optional[ScreenCaptureThread]
    processing_thread: threading.Thread
    inference_thread: threading.Thread


class AnalysisPipeline:
    def __init__(self, config: AppConfig, state: SharedState):
        self.config = config
        self.state = state
        self.frame_queue: queue.Queue[FramePacket] = queue.Queue(maxsize=4)
        self.detector = CandleDetector(max_candles=config.max_candles)
        self.predictor = EnsemblePredictor(sequence_length=config.sequence_length)
        self.predictor.load(config.model_dir)
        self._lock = threading.Lock()
        self._latest_features = None

    def select_roi(self) -> tuple[int, int, int, int]:
        import pyautogui
        import numpy as np

        shot = pyautogui.screenshot()
        img = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        rect = cv2.selectROI("Select chart ROI", img, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select chart ROI")
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            raise ValueError("ROI selection canceled.")
        return int(x), int(y), int(w), int(h)

    def start(self, record_training_data: bool = False) -> PipelineHandles:
        if not self.config.roi:
            self.config.roi = self.select_roi()

        capture = ScreenCaptureThread(self.frame_queue, roi=self.config.roi, fps=self.config.capture_fps)
        processing = threading.Thread(target=self._processing_loop, daemon=True)
        inference = threading.Thread(target=self._inference_loop, daemon=True)

        self._record_training_data = record_training_data

        capture.start()
        processing.start()
        inference.start()

        return PipelineHandles(capture_thread=capture, processing_thread=processing, inference_thread=inference)

    def _processing_loop(self) -> None:
        while self.state.running:
            try:
                packet = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            candles = self.detector.detect(packet.frame)
            with self._lock:
                self.state.latest_frame = packet.frame
                self.state.candles = candles[-self.config.max_candles :]
                self._latest_features = candles_to_feature_frame(self.state.candles)

                if self._record_training_data and self._latest_features is not None and not self._latest_features.empty:
                    save_ohlc_csv(self._latest_features.tail(1), self.config.ohlc_csv_path)

    def _inference_loop(self) -> None:
        while self.state.running:
            with self._lock:
                feat = self._latest_features.copy() if self._latest_features is not None else None
            if feat is not None and len(feat) >= self.config.min_candles_for_model:
                pred = self.predictor.predict(feat)
                with self._lock:
                    self.state.latest_prediction = pred
            time.sleep(0.2)

    def stop(self, handles: PipelineHandles) -> None:
        self.state.running = False
        if handles.capture_thread:
            handles.capture_thread.stop()
