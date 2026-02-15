from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    line = fast_ema - slow_ema
    signal_line = ema(line, signal)
    hist = line - signal_line
    return pd.DataFrame({"macd": line, "macd_signal": signal_line, "macd_hist": hist})


def bollinger(close: pd.Series, length: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    mid = sma(close, length)
    std = close.rolling(length).std()
    return pd.DataFrame({"bb_mid": mid, "bb_upper": mid + std_mult * std, "bb_lower": mid - std_mult * std})


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def stochastic(df: pd.DataFrame, length: int = 14, smooth: int = 3) -> pd.DataFrame:
    ll = df["low"].rolling(length).min()
    hh = df["high"].rolling(length).max()
    k = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    d = k.rolling(smooth).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": d})


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat([
        (df["high"] - df["low"]),
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1 / length, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / length, adjust=False).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / length, adjust=False).mean() / atr_val
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / length, adjust=False).mean()


def support_resistance(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    return pd.DataFrame({
        "support": df["low"].rolling(window).min(),
        "resistance": df["high"].rolling(window).max(),
    })


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema_9"] = ema(df["close"], 9)
    out["ema_21"] = ema(df["close"], 21)
    out["sma_20"] = sma(df["close"], 20)
    out["rsi_14"] = rsi(df["close"], 14)
    out = out.join(macd(df["close"]))
    out = out.join(bollinger(df["close"]))
    out["atr_14"] = atr(df, 14)
    out = out.join(stochastic(df, 14, 3))
    out = out.join(support_resistance(df, 20))
    out["adx_14"] = adx(df, 14)
    out["momentum_3"] = df["close"].pct_change(3)
    out["volatility_10"] = df["close"].pct_change().rolling(10).std()
    return out
