from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    capture_fps: int = 15
    min_capture_fps: int = 10
    max_capture_fps: int = 20
    max_candles: int = 100
    min_candles_for_prediction: int = 50
    sequence_length: int = 20
    resize_factor: float = 1.0
    roi: tuple[int, int, int, int] | None = None
    model_dir: Path = Path("models")
    training_csv: Path = Path("data/extracted_ohlc.csv")
    queue_size: int = 8
    use_gpu_if_available: bool = True


SAFETY_TEXT = (
    "Analysis-only tool. No clicks, broker automation, order execution, "
    "or software injection."
)
