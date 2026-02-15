from __future__ import annotations

from quotex_bot.config import RiskConfig, StrategyConfig
from quotex_bot.models import Prediction, Signal, SignalDecision


class RiskEngine:
    def __init__(self, strategy: StrategyConfig, risk: RiskConfig) -> None:
        self.strategy = strategy
        self.risk = risk
        self.daily_pnl = 0.0
        self.loss_streak = 0

    def register_trade_result(self, pnl: float) -> None:
        self.daily_pnl += pnl
        if pnl < 0:
            self.loss_streak += 1
        else:
            self.loss_streak = 0

    def decide(self, prediction: Prediction) -> SignalDecision:
        if self.daily_pnl <= -abs(self.risk.max_daily_loss):
            return SignalDecision(Signal.NO_TRADE, 0.0, "Daily loss limit reached")

        if self.loss_streak >= self.strategy.cooldown_after_losses:
            return SignalDecision(Signal.NO_TRADE, 0.0, "Cooldown after consecutive losses")

        if prediction.uncertainty > self.strategy.max_uncertainty:
            return SignalDecision(Signal.NO_TRADE, 1 - prediction.uncertainty, "High uncertainty")

        up_margin = prediction.p_up - prediction.p_down
        down_margin = prediction.p_down - prediction.p_up

        if prediction.p_up >= self.strategy.min_probability and up_margin >= self.strategy.min_margin:
            return SignalDecision(Signal.UP, prediction.p_up, "Probability and margin gate passed")

        if prediction.p_down >= self.strategy.min_probability and down_margin >= self.strategy.min_margin:
            return SignalDecision(Signal.DOWN, prediction.p_down, "Probability and margin gate passed")

        return SignalDecision(Signal.NO_TRADE, max(prediction.p_up, prediction.p_down), "No edge")
