from typing import Dict, List

import numpy as np


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    ema = np.zeros_like(values)
    ema[0] = values[0]
    for i in range(1, len(values)):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
    return ema


def compute_indicators(closes: List[float], highs: List[float], lows: List[float]) -> Dict[str, float]:
    c = np.asarray(closes, dtype=float)
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)

    diff = np.diff(c, prepend=c[0])
    gains = np.where(diff > 0, diff, 0)
    losses = np.where(diff < 0, -diff, 0)
    rsi_period = min(14, len(c) - 1) if len(c) > 1 else 1
    avg_gain = np.mean(gains[-rsi_period:])
    avg_loss = np.mean(losses[-rsi_period:]) + 1e-6
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    ema12 = _ema(c, min(12, len(c)))
    ema26 = _ema(c, min(26, len(c)))
    macd_line = float(ema12[-1] - ema26[-1])

    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    atr = float(np.mean(tr[-min(14, len(tr)):]))
    adx = float(min(100.0, (atr / (np.std(c[-min(20, len(c)):]) + 1e-6)) * 10))

    volatility = float(np.std(c[-min(20, len(c)):]))
    trend = float((c[-1] - c[-min(20, len(c))]) / (abs(c[-min(20, len(c))]) + 1e-6))

    return {
        "rsi": round(float(rsi), 2),
        "macd": round(macd_line, 4),
        "adx": round(adx, 2),
        "volatility": round(volatility, 4),
        "trend": round(trend, 4),
    }
