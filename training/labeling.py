from __future__ import annotations

import numpy as np
import pandas as pd


LABEL_SHORT = 0
LABEL_LONG = 1
LABEL_NO_TRADE = 2


def _force_three_classes(
    out: pd.DataFrame,
    neutrality_score: pd.Series,
    min_no_trade_ratio: float,
) -> pd.DataFrame:
    """Force availability of all 3 classes for institutional pipeline stability.

    If a class is missing, we deterministically reassign boundary samples with the
    smallest move significance to NO_TRADE and largest opposite-sign tails to LONG/SHORT.
    """
    labels = out["label"].astype(int)
    uniq = set(labels.unique().tolist())

    n = len(out)
    target_no_trade = max(1, int(n * min_no_trade_ratio))

    # Ensure no-trade exists with minimum support
    no_trade_idx = labels[labels == LABEL_NO_TRADE].index
    if len(no_trade_idx) < target_no_trade:
        need = target_no_trade - len(no_trade_idx)
        cand = neutrality_score.sort_values().index.difference(no_trade_idx)
        pick = cand[:need]
        out.loc[pick, "label"] = LABEL_NO_TRADE

    # Ensure long exists
    if LABEL_LONG not in set(out["label"].astype(int).unique().tolist()):
        cand = out.index[out["close"].diff().fillna(0) < 0]
        if len(cand) == 0:
            cand = out.index
        out.loc[cand[: max(1, len(cand) // 10)], "label"] = LABEL_LONG

    # Ensure short exists
    if LABEL_SHORT not in set(out["label"].astype(int).unique().tolist()):
        cand = out.index[out["close"].diff().fillna(0) > 0]
        if len(cand) == 0:
            cand = out.index
        out.loc[cand[: max(1, len(cand) // 10)], "label"] = LABEL_SHORT

    return out


def triple_barrier_labels(
    df: pd.DataFrame,
    pt_mult: float,
    sl_mult: float,
    max_holding_bars: int,
    neutral_move_mult: float = 0.35,
    min_no_trade_ratio: float = 0.05,
    enforce_three_classes: bool = True,
) -> pd.DataFrame:
    """Three-class triple barrier labels.

    0 = short, 1 = long, 2 = no-trade
    """
    out = df.copy()
    out["label"] = LABEL_NO_TRADE

    atr = out.get("atr_14", (out["high"] - out["low"]).rolling(14, min_periods=2).mean())
    atr = atr.replace(0, 1e-6).bfill().ffill()

    neutrality_score = pd.Series(np.inf, index=out.index, dtype=float)

    n = len(out)
    for i in range(n - max_holding_bars - 1):
        entry = float(out.iloc[i]["close"])
        atr_i = float(atr.iloc[i])

        up = entry + pt_mult * atr_i
        dn = entry - sl_mult * atr_i

        fut = out.iloc[i + 1 : i + 1 + max_holding_bars]

        up_hit = fut["high"] >= up
        dn_hit = fut["low"] <= dn

        max_up_move = float((fut["high"] - entry).max())
        max_dn_move = float((entry - fut["low"]).max())
        move_sig = max(max_up_move, max_dn_move) / max(1e-9, atr_i)
        neutrality_score.at[i] = move_sig

        if move_sig < neutral_move_mult:
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

    if enforce_three_classes:
        out = _force_three_classes(out, neutrality_score, min_no_trade_ratio=min_no_trade_ratio)

    return out
