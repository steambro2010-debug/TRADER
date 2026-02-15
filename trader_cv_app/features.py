from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .data_models import Candle


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss.replace(0, np.nan))
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _candle_pattern(df: pd.DataFrame) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    candle_range = (df["high"] - df["low"]).replace(0, np.nan)
    doji = (body / candle_range) < 0.1
    hammer = ((df["close"] > df["open"]) & ((df["open"] - df["low"]) > 2 * body))
    signal = np.zeros(len(df))
    signal[doji.fillna(False)] = 1
    signal[hammer.fillna(False)] = 2
    return pd.Series(signal, index=df.index)


def candles_to_feature_frame(candles: List[Candle]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "timestamp": [c.timestamp for c in candles],
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
        }
    )

    df["rsi_14"] = _rsi(df["close"], 14)
    for p in (9, 21, 50):
        df[f"ema_{p}"] = _ema(df["close"], p)

    macd_fast = _ema(df["close"], 12)
    macd_slow = _ema(df["close"], 26)
    df["macd"] = macd_fast - macd_slow
    df["macd_signal"] = _ema(df["macd"], 9)

    rolling_mean = df["close"].rolling(20).mean()
    rolling_std = df["close"].rolling(20).std()
    df["bb_mid"] = rolling_mean
    df["bb_upper"] = rolling_mean + (2 * rolling_std)
    df["bb_lower"] = rolling_mean - (2 * rolling_std)

    df["atr_14"] = _atr(df, 14)
    df["candle_pattern"] = _candle_pattern(df)

    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    return df.dropna().reset_index(drop=True)
