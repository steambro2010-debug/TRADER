from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    bullish: bool
    body_top_px: int
    body_bottom_px: int


@dataclass
class FeatureRow:
    timestamp: datetime
    values: dict


@dataclass
class PredictionResult:
    bullish_probability: float
    bearish_probability: float
    confidence: float
    model_breakdown: dict = field(default_factory=dict)


@dataclass
class SharedState:
    candles: List[Candle] = field(default_factory=list)
    latest_frame: Optional[object] = None
    latest_prediction: Optional[PredictionResult] = None
    running: bool = True
