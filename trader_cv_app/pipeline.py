from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

from .capture import ScreenCaptureWorker, select_roi_interactive
from .config import AppConfig
from .data_models import ModelStatus, PipelineStatus, SharedState
from .features import build_feature_frame, candles_to_dataframe
from .model import EnsembleModel, InferenceWorker
from .vision import CandleVisionWorker

logger = logging.getLogger(__name__)


class PipelineController:
    def __init__(self, config: AppConfig, state: SharedState):
        self.config = config
        self.state = state
        self.frame_queue = queue.Queue(maxsize=config.queue_size)
        self.candle_queue = queue.Queue(maxsize=config.queue_size)
        self.feature_queue = queue.Queue(maxsize=config.queue_size)
        self.prediction_queue = queue.Queue(maxsize=config.queue_size)
        self.error_queue = queue.Queue(maxsize=config.queue_size)

        self.capture_worker = None
        self.vision_worker = None
        self.inference_worker = None

        self.ensemble = EnsembleModel(config.model_dir, config.sequence_length)
        self.ensemble.load()
        self.state.model_status = self.ensemble.status
        self.state.model_message = self.ensemble.message

        self._record_training = False
        self._router_stop = threading.Event()
        self.router_thread = threading.Thread(target=self._router_loop, daemon=True)

    def start(self, record_training_data: bool = False) -> None:
        if self.capture_worker and self.capture_worker.is_alive():
            return

        if not self.config.roi:
            self.state.pipeline_status = PipelineStatus.LOADING
            self.state.pipeline_message = "Select ROI..."
            self.config.roi = select_roi_interactive()

        self._record_training = record_training_data
        self._router_stop.clear()

        self.capture_worker = ScreenCaptureWorker(
            self.frame_queue,
            self.error_queue,
            self.config.roi,
            fps=self.config.capture_fps,
            resize_factor=self.config.resize_factor,
        )
        self.vision_worker = CandleVisionWorker(self.frame_queue, self.candle_queue, self.error_queue, self.config.max_candles)
        self.inference_worker = InferenceWorker(self.feature_queue, self.prediction_queue, self.error_queue, self.ensemble)

        self.capture_worker.start()
        self.vision_worker.start()
        self.inference_worker.start()
        if not self.router_thread.is_alive():
            self.router_thread = threading.Thread(target=self._router_loop, daemon=True)
            self.router_thread.start()

        self.state.pipeline_status = PipelineStatus.RUNNING
        self.state.pipeline_message = "Running"

    def stop(self) -> None:
        self._router_stop.set()
        if self.capture_worker:
            self.capture_worker.stop()
        if self.vision_worker:
            self.vision_worker.stop()
        if self.inference_worker:
            self.inference_worker.stop()
        self.state.pipeline_status = PipelineStatus.STOPPED
        self.state.pipeline_message = "Stopped"

    def train_offline(self) -> tuple[bool, str]:
        ok, msg = self.ensemble.train_from_csv(self.config.training_csv)
        self.state.model_status = self.ensemble.status
        self.state.model_message = self.ensemble.message
        return ok, msg

    def _router_loop(self) -> None:
        while not self._router_stop.is_set():
            self._drain_candles()
            self._drain_predictions()
            self._drain_errors()
            self._restart_crashed_threads()

    def _drain_candles(self) -> None:
        try:
            payload = self.candle_queue.get_nowait()
        except queue.Empty:
            return

        self.state.latest_frame = payload["frame"]
        self.state.candles = payload["candles"][-self.config.max_candles :]
        self.state.capture_fps = payload["fps"]

        if not self.state.candles:
            self.state.pipeline_status = PipelineStatus.WARNING
            self.state.pipeline_message = "No candles detected"
            return

        if self.state.pipeline_status != PipelineStatus.ERROR:
            self.state.pipeline_status = PipelineStatus.RUNNING
            self.state.pipeline_message = "Live"

        base_df = candles_to_dataframe(self.state.candles)
        feature_df = build_feature_frame(base_df)

        if self._record_training and not feature_df.empty:
            self._append_training_row(feature_df.tail(1))

        if len(self.state.candles) >= self.config.min_candles_for_prediction and not feature_df.empty:
            if self.feature_queue.full():
                self.feature_queue.get_nowait()
            self.feature_queue.put_nowait(feature_df)

    def _drain_predictions(self) -> None:
        try:
            pred = self.prediction_queue.get_nowait()
        except queue.Empty:
            return
        self.state.prediction = pred

    def _drain_errors(self) -> None:
        updated = False
        while True:
            try:
                err = self.error_queue.get_nowait()
            except queue.Empty:
                break
            self.state.pipeline_status = PipelineStatus.ERROR if "failed" in str(err).lower() else PipelineStatus.WARNING
            if isinstance(err, dict):
                self.state.pipeline_message = err.get("message", "Pipeline warning")
            else:
                self.state.pipeline_message = str(err)
            updated = True
        if updated:
            logger.warning("Pipeline status: %s", self.state.pipeline_message)

    def _restart_crashed_threads(self) -> None:
        if self.capture_worker and not self.capture_worker.is_alive():
            logger.error("Capture worker crashed; restarting")
            self.capture_worker = ScreenCaptureWorker(
                self.frame_queue,
                self.error_queue,
                self.config.roi,
                fps=self.config.capture_fps,
                resize_factor=self.config.resize_factor,
            )
            self.capture_worker.start()

        if self.vision_worker and not self.vision_worker.is_alive():
            logger.error("Vision worker crashed; restarting")
            self.vision_worker = CandleVisionWorker(self.frame_queue, self.candle_queue, self.error_queue, self.config.max_candles)
            self.vision_worker.start()

        if self.inference_worker and not self.inference_worker.is_alive():
            logger.error("Inference worker crashed; restarting")
            self.inference_worker = InferenceWorker(self.feature_queue, self.prediction_queue, self.error_queue, self.ensemble)
            self.inference_worker.start()

    def _append_training_row(self, df_row) -> None:
        path = Path(self.config.training_csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        df_row.to_csv(path, mode="a", header=write_header, index=False)
