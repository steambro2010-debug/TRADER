from __future__ import annotations

import pandas as pd


LABEL_SHORT = 0
LABEL_LONG = 1
LABEL_NO_TRADE = 2


def triple_barrier_labels(
    df: pd.DataFrame,
    pt_mult: float,
    sl_mult: float,
    max_holding_bars: int,
    neutral_move_mult: float = 0.35,
) -> pd.DataFrame:
    """Three-class triple barrier labels.

    0 = short, 1 = long, 2 = no-trade
    """
    out = df.copy()
    out["label"] = LABEL_NO_TRADE

    atr = out.get("atr_14", (out["high"] - out["low"]).rolling(14, min_periods=2).mean())
    atr = atr.replace(0, 1e-6).bfill().ffill()

    n = len(out)
    for i in range(n - max_holding_bars - 1):
        entry = float(out.iloc[i]["close"])
        atr_i = float(atr.iloc[i])

        up = entry + pt_mult * atr_i
        dn = entry - sl_mult * atr_i

        fut = out.iloc[i + 1 : i + 1 + max_holding_bars]

        up_hit = fut["high"] >= up
        dn_hit = fut["low"] <= dn

        # explicit no-trade zone: market never moved enough to express direction
        max_up_move = float((fut["high"] - entry).max())
        max_dn_move = float((entry - fut["low"]).max())
        if max(max_up_move, max_dn_move) < neutral_move_mult * atr_i:
            out.at[i, "label"] = LABEL_NO_TRADE
            continue

        if up_hit.any() and dn_hit.any():
            up_idx = int(up_hit.idxmax())
            dn_idx = int(dn_hit.idxmax())
            if up_idx == dn_idx:
                out.at[i, "label"] = LABEL_NO_TRADE
            else:
                out.at[i, "label"] = LABEL_LONG if up_idx < dn_idx else LABEL_SHORT
        elif up_hit.any():
            out.at[i, "label"] = LABEL_LONG
        elif dn_hit.any():
            out.at[i, "label"] = LABEL_SHORT
        else:
            out.at[i, "label"] = LABEL_NO_TRADE

    return out
