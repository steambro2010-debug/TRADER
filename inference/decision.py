from __future__ import annotations

import numpy as np
import pandas as pd


def apply_decision_rules(row: pd.Series, probs: np.ndarray, uncertainty: float, cfg: dict) -> tuple[np.ndarray, str]:
    dcfg = cfg["decision"]
    regime = str(row.get("regime_tag", "default"))
    threshold = float(dcfg["regime_thresholds"].get(regime, dcfg["regime_thresholds"]["default"]))

    p_short, p_long, p_no = map(float, probs)
    reasons = []

    if uncertainty > float(dcfg["max_uncertainty"]):
        p_no = max(p_no, 0.8)
        reasons.append("uncertainty")

    if dcfg.get("require_mtf_agreement", True):
        agree = abs(row.get("tf_1h_ret", 0) + row.get("tf_4h_ret", 0)) > 1e-4
        if not agree:
            p_no = max(p_no, 0.7)
            reasons.append("mtf_disagree")

    if max(p_short, p_long) < threshold:
        p_no = max(p_no, 0.7)
        reasons.append("edge_low")

    adj = np.array([p_short, p_long, p_no], dtype=float)
    adj = adj / adj.sum()
    return adj, ",".join(reasons) if reasons else "ok"
