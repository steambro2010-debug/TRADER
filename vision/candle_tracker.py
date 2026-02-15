import queue
import threading
import time
from typing import Optional

from data.buffer import Candle, CandleBuffer
from vision.candle_detector import CandleDetector


class CandleTracker:
    def __init__(
        self,
        frame_queue: queue.Queue,
        signal_queue: queue.Queue,
        candle_buffer: CandleBuffer,
        detector: CandleDetector,
        candle_duration_sec: int,
        metrics: dict,
        logger,
    ) -> None:
        self.frame_queue = frame_queue
        self.signal_queue = signal_queue
        self.candle_buffer = candle_buffer
        self.detector = detector
        self.candle_duration_sec = candle_duration_sec
        self.metrics = metrics
        self.logger = logger
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.last_emit_time = 0.0

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="vision-thread", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        self.logger.info("Candle tracker started")
        while not self.stop_event.is_set():
            try:
                timestamp, frame = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            signal = self.detector.process(frame)
            interval_elapsed = (timestamp - self.last_emit_time) >= self.candle_duration_sec
            if signal.is_new_candle or interval_elapsed:
                o, h, l, c = signal.ohlc
                self.candle_buffer.append(Candle(timestamp=timestamp, open=o, high=h, low=l, close=c))
                self.last_emit_time = timestamp
                self.metrics["buffer_size"] = self.candle_buffer.size()
                if self.signal_queue.full():
                    try:
                        self.signal_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.signal_queue.put({"timestamp": timestamp, "reason": "shift" if signal.is_new_candle else "interval"})

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
