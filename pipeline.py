from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import numpy as np

from config.settings import Settings
from data.loader import aggregate_timeframes, load_ohlcv, preprocess
from features.structural import build_features
from inference.decision import apply_decision_rules
from logger import get_logger
from models.ensemble import EnsembleModel
from risk.backtest import run_cost_aware_backtest
from risk.engine import RiskEngine
from training.labeling import triple_barrier_labels
from training.validation import walk_forward_splits


class MarketIntelligencePipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        level = 10 if settings.debug else 20
        self.log = get_logger("pipeline", level=level)

    def run(self, input_csv: str, output_json: str) -> dict:
        cfg = self.settings.raw
        self._set_deterministic(cfg)

        self.log.info("stage=start", extra={"stage": "start"})
        raw = load_ohlcv(input_csv)
        self.log.info(f"loaded_rows={len(raw)}", extra={"stage": "load_data"})

        if self.settings.debug:
            n = int(cfg["debug"].get("sample_rows", 2000))
            raw = raw.tail(n).reset_index(drop=True)
            self.log.info(f"debug_sample_rows={len(raw)}", extra={"stage": "debug"})

        proc = preprocess(raw, cfg["data"]["base_freq"])
        self.log.info(f"preprocess_shape={proc.shape}", extra={"stage": "preprocess"})

        frames = aggregate_timeframes(proc, cfg["data"]["timeframes"])
        feats = build_features(frames, cfg["features"]["windows"])
        self.log.info(f"feature_shape={feats.shape}", extra={"stage": "features"})

        labeled = triple_barrier_labels(
            feats,
            pt_mult=float(cfg["training"]["labeling"]["pt_mult"]),
            sl_mult=float(cfg["training"]["labeling"]["sl_mult"]),
            max_holding_bars=int(cfg["training"]["labeling"]["max_holding_bars"]),
        )
        self.log.info("labels_built", extra={"stage": "labeling"})

        feature_cols = [
            c
            for c in labeled.columns
            if c
            not in {
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "label",
                "position",
                "regime_tag",
            }
            and np.issubdtype(labeled[c].dtype, np.number)
        ]

        split = int(len(labeled) * float(cfg["training"]["train_ratio"]))
        train_df = labeled.iloc[:split].copy()
        test_df = labeled.iloc[split:].copy()

        model = EnsembleModel(cfg["models"]["tree"])
        model.fit(train_df, feature_cols)
        self.log.info("model_trained", extra={"stage": "train"})

        # walk-forward diagnostics
        wf_losses = []
        for tr_idx, te_idx in walk_forward_splits(train_df, n_splits=3):
            tr = train_df.iloc[tr_idx]
            te = train_df.iloc[te_idx]
            m = EnsembleModel(cfg["models"]["tree"])
            m.fit(tr, feature_cols)
            p, _ = m.predict_proba(te)
            y = te["label"].values
            # safe pseudo log-loss with clipping
            p_clip = np.clip(p, 1e-6, 1 - 1e-6)
            ll = -np.mean(np.log(p_clip[np.arange(len(y)), y]))
            wf_losses.append(float(ll))
        self.log.info(f"walk_forward_logloss={np.mean(wf_losses):.6f}", extra={"stage": "validate"})

        probs, un = model.predict_proba(test_df)
        risk = RiskEngine(cfg)

        positions = []
        decisions = []
        for i, (_, row) in enumerate(test_df.iterrows()):
            adj, reason = apply_decision_rules(row, probs[i], float(un[i]), cfg)
            p_short, p_long, p_no = map(float, adj)

            regime = str(row.get("regime_tag", "transitional"))
            mult = risk.multiplier(p_long, p_short, p_no, regime, float(un[i]))
            if risk.observation_mode():
                mult = 0.0
                reason = f"observation_mode,{reason}"

            if p_no >= max(p_long, p_short):
                bias, side = "NO_TRADE", 0
            elif p_long > p_short:
                bias, side = "LONG", 1
            else:
                bias, side = "SHORT", -1

            pos = side * mult
            positions.append(pos)

            decisions.append(
                {
                    "timestamp": str(row["timestamp"]),
                    "regime": regime,
                    "structural_bias": bias,
                    "p_long": p_long,
                    "p_short": p_short,
                    "p_no_trade": p_no,
                    "uncertainty": float(un[i]),
                    "risk_multiplier": float(mult),
                    "confidence_percentile": float(np.percentile(probs[:, 1], p_long * 100)) if len(probs) else 0.0,
                    "recommended_position_size": float(mult * cfg["risk"]["base_risk_unit"]),
                    "decision_reason": reason,
                }
            )

        test_df["position"] = positions
        metrics = run_cost_aware_backtest(test_df, cfg)
        metrics["walk_forward_logloss"] = float(np.mean(wf_losses))

        payload = {
            "metrics": metrics,
            "decisions": decisions[-int(cfg["output"]["last_n_decisions"]):],
        }
        Path(output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.log.info("pipeline_complete", extra={"stage": "output"})
        return payload

    def _set_deterministic(self, cfg: dict):
        seed = int(cfg.get("runtime", {}).get("seed", 42))
        np.random.seed(seed)
        random.seed(seed)
