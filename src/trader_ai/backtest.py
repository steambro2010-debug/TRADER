from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class SignalRecord:
    predicted: int
    actual: int


class RollingAccuracy:
    def __init__(self, window: int = 100) -> None:
        self.window = window
        self.records: deque[SignalRecord] = deque(maxlen=window)

    def add(self, predicted: int, actual: int) -> None:
        self.records.append(SignalRecord(predicted=predicted, actual=actual))

    @property
    def value(self) -> float:
        if not self.records:
            return 0.0
        correct = sum(1 for r in self.records if r.predicted == r.actual)
        return correct / len(self.records)
