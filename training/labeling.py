from __future__ import annotations

import pandas as pd


def triple_barrier_labels(df: pd.DataFrame, pt_mult: float, sl_mult: float, max_holding_bars: int) -> pd.DataFrame:
    out = df.copy()
    out["label"] = 2
    atr = out.get("atr_14", (out["high"] - out["low"]).rolling(14, min_periods=2).mean()).replace(0, 1e-6).fillna(method="bfill")

    for i in range(len(out) - max_holding_bars - 1):
        entry = out.iloc[i]["close"]
        up = entry + pt_mult * atr.iloc[i]
        dn = entry - sl_mult * atr.iloc[i]
        fut = out.iloc[i + 1 : i + 1 + max_holding_bars]

        up_hit = (fut["high"] >= up)
        dn_hit = (fut["low"] <= dn)
        if up_hit.any() and dn_hit.any():
            out.at[i, "label"] = 1 if up_hit.idxmax() < dn_hit.idxmax() else 0
        elif up_hit.any():
            out.at[i, "label"] = 1
        elif dn_hit.any():
            out.at[i, "label"] = 0
        else:
            out.at[i, "label"] = 2

    return out
