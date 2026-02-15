from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import numpy as np


class ModelStatus(str, Enum):
    UNTRAINED = "UNTRAINED"
    READY = "READY"
    TRAINING = "TRAINING"
    ERROR = "ERROR"


class PipelineStatus(str, Enum):
    LOADING = "LOADING"
    RUNNING = "RUNNING"
    WARNING = "WARNING"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    bullish: bool
    x_center: int


@dataclass
class FramePacket:
    frame: np.ndarray
    timestamp: float
    fps: float


@dataclass
class PredictionResult:
    bullish_probability: float
    bearish_probability: float
    confidence: float
    model_breakdown: dict = field(default_factory=dict)


@dataclass
class SharedState:
    latest_frame: Optional[np.ndarray] = None
    candles: List[Candle] = field(default_factory=list)
    prediction: Optional[PredictionResult] = None
    capture_fps: float = 0.0
    pipeline_status: PipelineStatus = PipelineStatus.LOADING
    pipeline_message: str = "Initializing..."
    model_status: ModelStatus = ModelStatus.UNTRAINED
    model_message: str = "No trained model loaded"
