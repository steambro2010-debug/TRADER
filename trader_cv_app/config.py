from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    capture_fps: int = 8
    max_candles: int = 200
    min_candles_for_model: int = 50
    roi: tuple[int, int, int, int] | None = None
    use_gpu_if_available: bool = True
    ohlc_csv_path: str = "recorded_ohlc.csv"
    model_dir: str = "models"
    sequence_length: int = 20


DISCLAIMER = (
    "Safety constraint: Analysis-only tool. It does not automate, control, click, "
    "or inject into broker or charting software."
)
