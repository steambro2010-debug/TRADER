from __future__ import annotations

from quotex_bot.analysis import TrendAnalyzer
from quotex_bot.broker import BrokerAdapter, OrderResult
from quotex_bot.config import RiskConfig, StrategyConfig
from quotex_bot.models import CandleSeq, Signal, SignalDecision
from quotex_bot.risk import RiskEngine


class TradingEngine:
    def __init__(self, analyzer: TrendAnalyzer, risk_engine: RiskEngine, broker: BrokerAdapter) -> None:
        self.analyzer = analyzer
        self.risk_engine = risk_engine
        self.broker = broker

    @classmethod
    def default(cls, broker: BrokerAdapter) -> "TradingEngine":
        strategy = StrategyConfig()
        risk = RiskConfig()
        return cls(TrendAnalyzer(strategy), RiskEngine(strategy, risk), broker)

    def on_candles(self, candles: CandleSeq, execute: bool = False) -> tuple[SignalDecision, OrderResult | None]:
        prediction = self.analyzer.predict(candles)
        decision = self.risk_engine.decide(prediction)

        if not execute or decision.signal == Signal.NO_TRADE:
            return decision, None

        order_id = self.broker.place_order(decision.signal, amount=10.0, expiry_s=60)
        result = self.broker.settle_order(order_id)
        self.risk_engine.register_trade_result(result.pnl)
        return decision, result
