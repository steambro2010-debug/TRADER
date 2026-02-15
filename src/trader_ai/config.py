from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class CaptureConfig:
    fps_target: int = 12
    monitor_index: int = 1
    selected_region: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h


@dataclass
class ExtractorConfig:
    min_body_area: int = 35
    max_candles_per_frame: int = 100
    bullish_hsv_low: Tuple[int, int, int] = (35, 40, 40)
    bullish_hsv_high: Tuple[int, int, int] = (90, 255, 255)
    bearish_hsv_low: Tuple[int, int, int] = (0, 60, 40)
    bearish_hsv_high: Tuple[int, int, int] = (15, 255, 255)
    price_min: Optional[float] = None
    price_max: Optional[float] = None


@dataclass
class PipelineConfig:
    min_candles_for_features: int = 80
    sequence_length: int = 30
    prediction_enabled: bool = True
    log_dir: Path = field(default_factory=lambda: Path("data"))
    models_dir: Path = field(default_factory=lambda: Path("models"))
    rolling_accuracy_window: int = 100


@dataclass
class AppConfig:
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    extractor: ExtractorConfig = field(default_factory=ExtractorConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
