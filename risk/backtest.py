from __future__ import annotations

import numpy as np
import pandas as pd


def run_cost_aware_backtest(df: pd.DataFrame, cfg: dict) -> dict:
    b = cfg["backtest"]
    spread = float(b["spread_bps"]) / 10000.0
    slip = float(b["slippage_bps"]) / 10000.0
    latency = int(b["latency_bars"])

    pnl = []
    for i in range(latency, len(df)-1):
        pos = float(df.iloc[i]["position"])
        if pos == 0:
            pnl.append(0.0)
            continue
        ret = (df.iloc[i+1]["close"] - df.iloc[i]["close"]) / df.iloc[i]["close"]
        pnl.append(pos * ret - spread - slip)

    pnl = np.array(pnl)
    eq = np.cumprod(1 + pnl) if len(pnl) else np.array([1.0])
    dd = 1 - eq / np.maximum.accumulate(eq)
    sharpe = (np.mean(pnl) / (np.std(pnl)+1e-9)) * np.sqrt(252*24*60) if len(pnl) else 0.0
    sortino = (np.mean(pnl) / (np.std(np.clip(pnl, None, 0))+1e-9)) * np.sqrt(252*24*60) if len(pnl) else 0.0
    calmar = ((eq[-1]-1) / (dd.max()+1e-9)) if len(dd) else 0.0
    return {
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "calmar": float(calmar),
        "expectancy": float(np.mean(pnl) if len(pnl) else 0.0),
        "max_drawdown": float(dd.max() if len(dd) else 0.0),
    }
