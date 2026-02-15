from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from quotex_bot.models import Signal


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    direction: Signal
    amount: float
    won: bool
    pnl: float


class BrokerAdapter(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, direction: Signal, amount: float, expiry_s: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def settle_order(self, order_id: str) -> OrderResult:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self) -> None:
        self._idx = 0

    def connect(self) -> None:
        return None

    def place_order(self, direction: Signal, amount: float, expiry_s: int) -> str:
        self._idx += 1
        return f"paper-{self._idx}"

    def settle_order(self, order_id: str) -> OrderResult:
        # Placeholder deterministic result for local testing.
        won = self._idx % 2 == 0
        pnl = 8.0 if won else -10.0
        direction = Signal.UP if self._idx % 2 == 0 else Signal.DOWN
        return OrderResult(order_id=order_id, direction=direction, amount=10.0, won=won, pnl=pnl)
