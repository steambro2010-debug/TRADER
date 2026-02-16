from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class RiskState:
    equity: float = 1.0
    peak: float = 1.0
    drawdown: float = 0.0
    consecutive_losses: int = 0
    rolling_exp: float = 0.0


class RiskEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg["risk"]
        self.state = RiskState()

    def multiplier(self, p_long: float, p_short: float, p_no: float, regime: str, uncertainty: float) -> float:
        edge = max(p_long, p_short) - 0.5
        kelly = np.clip(2 * edge, 0, float(self.cfg["kelly_cap"]))
        regime_scale = {
            "trend_expansion": 1.0,
            "structured_trend": 0.9,
            "range_compression": 0.6,
            "volatility_expansion": 0.45,
            "transitional": 0.5,
            "low_vol_chop": 0.35,
        }.get(regime, 0.5)
        un_scale = np.clip(1 - 2 * uncertainty, 0.1, 1.0)
        dd_scale = np.clip(1 - self.state.drawdown / max(float(self.cfg["max_drawdown"]), 1e-9), 0, 1)
        return float(np.clip(kelly * regime_scale * un_scale * (1 - p_no) * dd_scale, 0, 1))

    def update(self, pnl: float):
        self.state.equity *= 1 + pnl
        self.state.peak = max(self.state.peak, self.state.equity)
        self.state.drawdown = 1 - self.state.equity / self.state.peak
        self.state.consecutive_losses = self.state.consecutive_losses + 1 if pnl < 0 else 0
        self.state.rolling_exp = 0.96 * self.state.rolling_exp + 0.04 * pnl

    def observation_mode(self) -> bool:
        if self.state.drawdown > float(self.cfg["max_drawdown"]) * float(self.cfg["dd_throttle"]):
            return True
        if self.state.consecutive_losses >= int(self.cfg["max_consecutive_losses"]):
            return True
        if self.state.rolling_exp < 0:
            return True
        return False
