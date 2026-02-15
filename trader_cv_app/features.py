from __future__ import annotations

import numpy as np
import pandas as pd

from .data_models import Candle


def candles_to_dataframe(candles: list[Candle]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "timestamp": [c.timestamp for c in candles],
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
            "bullish": [int(c.bullish) for c in candles],
        }
    )


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    out = df.copy()
    close = out["close"]

    out["rsi_14"] = rsi(close, 14)
    out["ema_9"] = close.ewm(span=9, adjust=False).mean()
    out["ema_21"] = close.ewm(span=21, adjust=False).mean()
    out["ema_50"] = close.ewm(span=50, adjust=False).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["bb_mid"] = mid
    out["bb_upper"] = mid + 2 * std
    out["bb_lower"] = mid - 2 * std

    out["atr_14"] = atr(out, 14)
    out["candle_pattern"] = candle_pattern_code(out)
    out["trend_slope"] = trend_slope(close, 14)
    out["volatility_regime"] = volatility_regime(close, 20)

    out["target"] = (out["close"].shift(-1) > out["close"]).astype(int)
    return out.dropna().reset_index(drop=True)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = np.maximum(high_low.values, np.maximum(high_close.values, low_close.values))
    return pd.Series(tr, index=df.index).rolling(period).mean()


def candle_pattern_code(df: pd.DataFrame) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    spread = (df["high"] - df["low"]).replace(0, np.nan)
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]

    doji = (body / spread) < 0.1
    hammer = (lower_wick > 2 * body) & (upper_wick < body)
    shooting_star = (upper_wick > 2 * body) & (lower_wick < body)

    code = np.zeros(len(df), dtype=float)
    code = np.where(doji.fillna(False), 1.0, code)
    code = np.where(hammer.fillna(False), 2.0, code)
    code = np.where(shooting_star.fillna(False), 3.0, code)
    return pd.Series(code, index=df.index)


def trend_slope(series: pd.Series, window: int = 14) -> pd.Series:
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    denom = np.sum((x - x_mean) ** 2)

    def _slope(values: np.ndarray) -> float:
        y = values.astype(float)
        y_mean = y.mean()
        return float(np.sum((x - x_mean) * (y - y_mean)) / denom)

    return series.rolling(window).apply(_slope, raw=True)


def volatility_regime(series: pd.Series, window: int = 20) -> pd.Series:
    vol = series.pct_change().rolling(window).std()
    threshold = vol.rolling(window).median()
    return (vol > threshold).astype(float)
