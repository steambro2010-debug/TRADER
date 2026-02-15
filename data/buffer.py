from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, List


@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float


class CandleBuffer:
    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._data: Deque[Candle] = deque(maxlen=capacity)
        self._lock = Lock()

    def append(self, candle: Candle) -> None:
        with self._lock:
            self._data.append(candle)

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def tail(self, count: int) -> List[Candle]:
        with self._lock:
            if count <= 0:
                return []
            return list(self._data)[-count:]

    def all(self) -> List[Candle]:
        with self._lock:
            return list(self._data)
