from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class Signal(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NO_TRADE = "NO-TRADE"


@dataclass(frozen=True)
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Prediction:
    p_up: float
    p_down: float
    uncertainty: float


@dataclass(frozen=True)
class SignalDecision:
    signal: Signal
    confidence: float
    reason: str


CandleSeq = List[Candle]
