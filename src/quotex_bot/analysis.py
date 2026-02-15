from __future__ import annotations

from math import exp

from quotex_bot.config import StrategyConfig
from quotex_bot.models import CandleSeq, Prediction


def _ema(values: list[float], period: int) -> float:
    if not values:
        raise ValueError("ema requires values")
    alpha = 2 / (period + 1)
    acc = values[0]
    for v in values[1:]:
        acc = (v * alpha) + (acc * (1 - alpha))
    return acc


def _rsi(closes: list[float], period: int) -> float:
    if len(closes) <= period:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


class TrendAnalyzer:
    """Baseline analyzer from candle history.

    This intentionally avoids direct broker integration and can be fed from
    OCR/CV extraction layers in a larger system.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def predict(self, candles: CandleSeq) -> Prediction:
        if len(candles) < max(self.config.ema_slow_period, self.config.rsi_period) + 2:
            return Prediction(p_up=0.34, p_down=0.34, uncertainty=0.9)

        closes = [c.close for c in candles]
        ema_fast = _ema(closes[-self.config.ema_fast_period * 2 :], self.config.ema_fast_period)
        ema_slow = _ema(closes[-self.config.ema_slow_period * 2 :], self.config.ema_slow_period)
        rsi = _rsi(closes, self.config.rsi_period)

        trend_strength = (ema_fast - ema_slow) / max(abs(ema_slow), 1e-9)
        trend_score = 1 / (1 + exp(-trend_strength * 180))

        momentum_score = (rsi - 50) / 50
        p_up = min(max((0.6 * trend_score) + (0.4 * (momentum_score + 1) / 2), 0.01), 0.99)
        p_down = 1 - p_up
        uncertainty = abs(0.5 - p_up) * -2 + 1
        return Prediction(p_up=p_up, p_down=p_down, uncertainty=max(0.0, min(1.0, uncertainty)))
