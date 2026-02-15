from __future__ import annotations

from dataclasses import dataclass
import logging
import time

from utils.config import RiskConfig
from utils.logger import append_csv


@dataclass
class TradeDecision:
    should_trade: bool
    reason: str
    stake: float


class TradeExecutor:
    def __init__(self, risk: RiskConfig, starting_balance: float = 1000.0) -> None:
        self.risk = risk
        self.balance = starting_balance
        self.loss_streak = 0
        self.trades_last_hour: list[float] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def evaluate_constraints(self, confidence: float, threshold: float) -> TradeDecision:
        now = time.time()
        self.trades_last_hour = [t for t in self.trades_last_hour if now - t < 3600]
        if confidence < threshold:
            return TradeDecision(False, "below threshold", 0.0)
        if len(self.trades_last_hour) >= self.risk.max_trades_per_hour:
            return TradeDecision(False, "max trades/hour reached", 0.0)
        if self.loss_streak >= self.risk.stop_loss_streak_limit:
            return TradeDecision(False, "stop-loss streak triggered", 0.0)

        stake = self.balance * self.risk.capital_pct
        if self.risk.martingale_enabled and self.loss_streak > 0:
            stake *= self.risk.martingale_multiplier ** self.loss_streak
        return TradeDecision(True, "ok", stake)

    def execute(self, direction: str, confidence: float, threshold: float, js_runner) -> TradeDecision:
        decision = self.evaluate_constraints(confidence, threshold)
        if not decision.should_trade:
            return decision

        button_selector = "button.call-btn" if direction == "UP" else "button.put-btn"
        confirm_selector = "div.deal-confirmation, div.order-result"
        script = f"""
        (() => {{
          const button = document.querySelector('{button_selector}');
          if (!button) return {{ok:false, reason:'button_not_found'}};
          button.click();
          const confirmed = !!document.querySelector('{confirm_selector}');
          return {{ok: true, confirmed}};
        }})();
        """

        time.sleep(0.15)
        js_runner(script)
        self.trades_last_hour.append(time.time())

        append_csv(
            "trades.csv",
            {
                "timestamp": time.time(),
                "direction": direction,
                "confidence": confidence,
                "stake": decision.stake,
                "result": "SUBMITTED",
            },
            headers=["timestamp", "direction", "confidence", "stake", "result"],
        )
        self.logger.info("Trade submitted: %s %.2f%% stake=%.2f", direction, confidence, decision.stake)
        return decision
