from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=2).mean()


def build_features(frames: dict[str, pd.DataFrame], windows: list[int]) -> pd.DataFrame:
    df = frames["1x"].copy()
    close = df["close"]
    ret = np.log(close).diff().fillna(0)

    # 150+ via window stack
    for w in windows:
        df[f"trend_z_{w}"] = (close - close.rolling(w, min_periods=max(4, w//4)).mean()) / close.rolling(w, min_periods=max(4, w//4)).std().replace(0, np.nan)
        df[f"rv_{w}"] = ret.rolling(w, min_periods=max(4, w//4)).std()
        df[f"entropy_{w}"] = _rolling_entropy(ret, w)
        df[f"dir_persist_{w}"] = ret.gt(0).rolling(w).mean()
        df[f"roc_{w}"] = close.pct_change(w).fillna(0)

    for p in [7, 14, 21, 30]:
        df[f"atr_{p}"] = _atr(df["high"], df["low"], close, p)

    # momentum hierarchy
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd"] = macd
    df["macd_d1"] = macd.diff()
    df["macd_d2"] = macd.diff().diff()
    df["macd_hist"] = macd - signal

    for rsi_w in [7, 14, 21, 34]:
        delta = close.diff()
        up = delta.clip(lower=0).rolling(rsi_w).mean()
        down = -delta.clip(upper=0).rolling(rsi_w).mean().replace(0, np.nan)
        rs = up / down
        df[f"rsi_{rsi_w}"] = 100 - (100 / (1 + rs))

    # candle microstructure
    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    df["body_range_ratio"] = (body / rng).fillna(0)
    df["close_location"] = ((df["close"] - df["low"]) / rng).fillna(0)
    df["inside_bar"] = ((df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))).astype(int)
    df["outside_bar"] = ((df["high"] > df["high"].shift(1)) & (df["low"] < df["low"].shift(1))).astype(int)

    # liquidity proxies
    hh = df["high"].rolling(15, min_periods=4).max()
    ll = df["low"].rolling(15, min_periods=4).min()
    df["liq_sweep_high"] = ((df["high"] > hh.shift(1)) & (df["close"] < hh.shift(1))).astype(int)
    df["liq_sweep_low"] = ((df["low"] < ll.shift(1)) & (df["close"] > ll.shift(1))).astype(int)
    df["fvg_bull"] = (df["low"].shift(-1) > df["high"].shift(1)).astype(int)
    df["fvg_bear"] = (df["high"].shift(-1) < df["low"].shift(1)).astype(int)

    # MTF merge
    for tf, frame in frames.items():
        if tf == "1x":
            continue
        tmp = frame[["timestamp", "log_return"]].copy().rename(columns={"log_return": f"tf_{tf}_ret"})
        df = pd.merge_asof(df.sort_values("timestamp"), tmp.sort_values("timestamp"), on="timestamp", direction="backward")

    # regime tags
    reg_cols = [c for c in df.columns if c.startswith("rv_") or c.startswith("trend_z_")]
    reg_mat = df[reg_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    gmm = GaussianMixture(n_components=6, random_state=11)
    df["regime_cluster"] = gmm.fit_predict(reg_mat)
    mapping = {0: "structured_trend", 1: "range_compression", 2: "volatility_expansion", 3: "trend_expansion", 4: "transitional", 5: "low_vol_chop"}
    df["regime_tag"] = df["regime_cluster"].map(mapping).fillna("transitional")

    return df.replace([np.inf, -np.inf], np.nan).fillna(0)


def _rolling_entropy(series: pd.Series, window: int) -> pd.Series:
    out = np.zeros(len(series), dtype=float)
    vals = series.values
    for i in range(window, len(vals)):
        seg = vals[i-window:i]
        hist, _ = np.histogram(seg, bins=10, density=True)
        p = hist / (hist.sum() + 1e-9)
        out[i] = -np.sum(p * np.log(p + 1e-9))
    return pd.Series(out, index=series.index)
