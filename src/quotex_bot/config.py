from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    min_probability: float = 0.62
    min_margin: float = 0.08
    max_uncertainty: float = 0.35
    cooldown_after_losses: int = 3
    ema_fast_period: int = 8
    ema_slow_period: int = 21
    rsi_period: int = 14


@dataclass(frozen=True)
class RiskConfig:
    max_daily_loss: float = 200.0
    risk_per_trade: float = 10.0
