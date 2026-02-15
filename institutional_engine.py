"""
Institutional-grade market structure intelligence engine.

Pipeline:
- Data architecture: OHLCV ingestion, multi-timeframe aggregation, normalization, fractional differentiation
- Deep structural feature engineering (150+ features)
- Regime intelligence + triple-barrier labeling
- Multi-branch model stack (tree + temporal branch) + calibrated ensemble
- Uncertainty-aware decision layer (P(long), P(short), P(no-trade))
- Risk intelligence engine + cost-aware backtesting
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler


@dataclass
class DecisionOutput:
    timestamp: str
    regime: str
    structural_bias: str
    p_long: float
    p_short: float
    p_no_trade: float
    uncertainty: float
    risk_multiplier: float
    confidence_percentile: float
    recommended_position_size: float


@dataclass
class BarrierConfig:
    pt_mult: float
    sl_mult: float
    max_holding_bars: int


@dataclass
class RiskState:
    equity: float = 1.0
    peak_equity: float = 1.0
    drawdown: float = 0.0
    consecutive_losses: int = 0
    rolling_expectancy: float = 0.0


class DataArchitecture:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.timeframes = cfg["data"]["timeframes"]
        self.frac_diff_d = float(cfg["data"]["fractional_diff_d"])

    def load_ohlcv(self, csv_path: str) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        required = {"timestamp", "open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        if "volume" not in df.columns:
            df["volume"] = 0.0

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        return df

    def handle_missing_and_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        full_idx = pd.date_range(df["timestamp"].iloc[0], df["timestamp"].iloc[-1], freq=self.cfg["data"]["base_freq"], tz="UTC")
        df = df.set_index("timestamp").reindex(full_idx)
        df.index.name = "timestamp"

        returns = np.log(df["close"]).diff()
        vol = returns.rolling(30, min_periods=5).std().fillna(returns.std())

        for col in ["open", "high", "low", "close", "volume"]:
            interp = df[col].interpolate(method="time", limit_direction="both")
            noise = (vol.fillna(0) * df["close"].fillna(method="ffill") * 0.05).fillna(0)
            df[col] = np.where(df[col].isna(), interp + noise, df[col])

        df["missing_flag"] = df[["open", "high", "low", "close"]].isna().any(axis=1).astype(int)
        df["gap_flag"] = ((df.index.to_series().diff().dt.total_seconds().fillna(0)) > pd.Timedelta(self.cfg["data"]["base_freq"]).total_seconds()).astype(int)

        out = df.reset_index()
        return out

    def add_core_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["log_return"] = np.log(out["close"]).diff().fillna(0)
        out["vol_norm_return"] = out["log_return"] / (out["log_return"].rolling(30, min_periods=5).std().replace(0, np.nan)).fillna(0)
        out["detrended_close"] = out["close"] - out["close"].rolling(100, min_periods=10).mean()
        out["frac_diff_close"] = self._fractional_diff(out["close"], self.frac_diff_d)
        return out

    def _fractional_diff(self, series: pd.Series, d: float, thresh: float = 1e-4) -> pd.Series:
        weights = [1.0]
        k = 1
        while True:
            w = -weights[-1] * (d - k + 1) / k
            if abs(w) < thresh:
                break
            weights.append(w)
            k += 1
        weights = np.array(weights[::-1])
        out = pd.Series(index=series.index, dtype=float)
        for i in range(len(weights), len(series) + 1):
            window = series.iloc[i - len(weights) : i]
            out.iloc[i - 1] = np.dot(weights, window)
        return out.fillna(0)

    def build_multi_timeframe(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        frames: Dict[str, pd.DataFrame] = {"1x": df.copy()}
        base = df.set_index("timestamp")

        tf_map = {
            "3x": "3T",
            "5x": "5T",
            "15x": "15T",
            "1h": "1H",
            "4h": "4H",
        }

        for tf in self.timeframes:
            if tf == "1x":
                continue
            rule = tf_map[tf]
            agg = base.resample(rule).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "missing_flag": "max",
                "gap_flag": "max",
            }).dropna()
            agg = agg.reset_index()
            agg["log_return"] = np.log(agg["close"]).diff().fillna(0)
            frames[tf] = agg
        return frames


class StructuralFeatureFactory:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.windows = cfg["features"]["windows"]

    def transform(self, frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        base = frames["1x"].copy()
        base = self._add_trend_structure(base)
        base = self._add_volatility_intelligence(base)
        base = self._add_momentum_hierarchy(base)
        base = self._add_candle_microstructure(base)
        base = self._add_liquidity_structure(base)

        for tf, frame in frames.items():
            if tf == "1x":
                continue
            tmp = frame[["timestamp", "close", "high", "low", "log_return"]].copy()
            tmp[f"tf_{tf}_ret"] = tmp["log_return"]
            tmp[f"tf_{tf}_atr"] = self._atr(tmp["high"], tmp["low"], tmp["close"], 14)
            tmp = tmp[["timestamp", f"tf_{tf}_ret", f"tf_{tf}_atr"]]
            base = pd.merge_asof(base.sort_values("timestamp"), tmp.sort_values("timestamp"), on="timestamp", direction="backward")

        base = self._add_regime_features(base)
        base = base.replace([np.inf, -np.inf], np.nan).fillna(0)
        return base

    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        return tr.rolling(period, min_periods=2).mean()

    def _add_trend_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        for w in self.windows:
            roll = df["close"].rolling(w, min_periods=max(4, w // 4))
            mean = roll.mean()
            std = roll.std().replace(0, np.nan)
            df[f"trend_z_{w}"] = (df["close"] - mean) / std
            df[f"trend_r2_{w}"] = self._rolling_r2(df["close"], w)
            df[f"hurst_{w}"] = self._hurst_approx(df["close"], w)
            df[f"fract_dim_{w}"] = 2 - df[f"hurst_{w}"].clip(0, 1)
            df[f"dir_persist_{w}"] = df["close"].diff().gt(0).rolling(w).mean()
            df[f"cusum_break_{w}"] = self._cusum_break(df["close"], w)

        highs = df["high"].rolling(10, min_periods=2).max()
        lows = df["low"].rolling(10, min_periods=2).min()
        df["higher_high_state"] = (df["high"] >= highs.shift(1)).astype(int)
        df["lower_low_state"] = (df["low"] <= lows.shift(1)).astype(int)
        return df

    def _add_volatility_intelligence(self, df: pd.DataFrame) -> pd.DataFrame:
        ret = np.log(df["close"]).diff().fillna(0)
        for w in self.windows:
            vol = ret.rolling(w, min_periods=max(4, w // 4)).std()
            df[f"rv_{w}"] = vol
            df[f"vov_{w}"] = vol.diff().abs().rolling(w, min_periods=2).mean()
            df[f"vol_pct_{w}"] = vol.rank(pct=True)
            df[f"entropy_{w}"] = self._rolling_entropy(ret, w)

        for p in [7, 14, 21, 30]:
            df[f"atr_{p}"] = self._atr(df["high"], df["low"], df["close"], p)
        df["range_exp_accel"] = (df["high"] - df["low"]).diff().diff().fillna(0)
        return df

    def _add_momentum_hierarchy(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        for w in [3, 5, 8, 13, 21, 34, 55]:
            df[f"roc_{w}"] = close.pct_change(w).fillna(0)

        for w in [7, 14, 21, 34]:
            delta = close.diff()
            up = delta.clip(lower=0).rolling(w).mean()
            down = -delta.clip(upper=0).rolling(w).mean().replace(0, np.nan)
            rs = up / down
            df[f"rsi_{w}"] = 100 - (100 / (1 + rs))
            df[f"rsi_slope_{w}"] = df[f"rsi_{w}"].diff()
            df[f"rsi_curve_{w}"] = df[f"rsi_{w}"].diff().diff()

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        df["macd"] = macd
        df["macd_d1"] = macd.diff()
        df["macd_d2"] = macd.diff().diff()
        df["macd_hist"] = hist

        for lag in range(1, 21):
            df[f"acf_lag_{lag}"] = close.diff().rolling(80).corr(close.diff().shift(lag)).fillna(0)

        df["momentum_exhaustion"] = ((df["rsi_14"] > 75) & (df["macd_d1"] < 0)).astype(int)
        df["momentum_divergence"] = np.sign(df["close"].diff(5)) != np.sign(df["rsi_14"].diff(5))
        df["momentum_divergence"] = df["momentum_divergence"].astype(int)
        return df

    def _add_candle_microstructure(self, df: pd.DataFrame) -> pd.DataFrame:
        body = (df["close"] - df["open"]).abs()
        rng = (df["high"] - df["low"]).replace(0, np.nan)
        upper_wick = (df[["open", "close"]].min(axis=1) - df["low"]).clip(lower=0)
        lower_wick = (df["high"] - df[["open", "close"]].max(axis=1)).clip(lower=0)

        df["body_range_ratio"] = (body / rng).fillna(0)
        df["wick_asymmetry"] = ((upper_wick - lower_wick) / rng).fillna(0)
        df["close_location"] = ((df["close"] - df["low"]) / rng).fillna(0)
        df["inside_bar"] = ((df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))).astype(int)
        df["outside_bar"] = ((df["high"] > df["high"].shift(1)) & (df["low"] < df["low"].shift(1))).astype(int)
        df["compression"] = (rng < rng.rolling(20, min_periods=5).quantile(0.25)).astype(int)
        df["expansion_impulse"] = (rng > rng.rolling(20, min_periods=5).quantile(0.8)).astype(int)
        return df

    def _add_liquidity_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        hh = df["high"].rolling(15, min_periods=4).max()
        ll = df["low"].rolling(15, min_periods=4).min()
        df["liq_sweep_high"] = ((df["high"] > hh.shift(1)) & (df["close"] < hh.shift(1))).astype(int)
        df["liq_sweep_low"] = ((df["low"] < ll.shift(1)) & (df["close"] > ll.shift(1))).astype(int)

        eqh = (df["high"].rolling(10).std() < df["high"].rolling(50).std() * 0.3).astype(int)
        eql = (df["low"].rolling(10).std() < df["low"].rolling(50).std() * 0.3).astype(int)
        df["equal_highs"] = eqh
        df["equal_lows"] = eql

        df["fvg_bull"] = (df["low"].shift(-1) > df["high"].shift(1)).astype(int)
        df["fvg_bear"] = (df["high"].shift(-1) < df["low"].shift(1)).astype(int)
        df["imbalance"] = ((df["close"] - df["open"]).abs() / (df["high"] - df["low"]).replace(0, np.nan)).fillna(0)

        swing_high = df["high"].rolling(8).max()
        swing_low = df["low"].rolling(8).min()
        df["dist_nearest_level"] = np.minimum((df["close"] - swing_low).abs(), (df["close"] - swing_high).abs())
        df["liquidity_vacuum_prob"] = ((df["expansion_impulse"] == 1) & (df["imbalance"] > 0.7)).astype(int)
        return df

    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        reg_feats = [c for c in df.columns if c.startswith("rv_") or c.startswith("trend_r2_") or c.startswith("hurst_")]
        z = df[reg_feats].fillna(0)
        gmm = GaussianMixture(n_components=6, random_state=7)
        labels = gmm.fit_predict(z)
        df["regime_cluster"] = labels
        return df

    def _rolling_r2(self, series: pd.Series, window: int) -> pd.Series:
        vals = series.values
        out = np.zeros_like(vals, dtype=float)
        x = np.arange(window)
        for i in range(window, len(vals)):
            y = vals[i - window : i]
            slope, intercept = np.polyfit(x, y, 1)
            y_hat = slope * x + intercept
            ss_res = np.sum((y - y_hat) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2) + 1e-9
            out[i] = 1 - ss_res / ss_tot
        return pd.Series(out, index=series.index)

    def _hurst_approx(self, series: pd.Series, window: int) -> pd.Series:
        out = np.zeros(len(series), dtype=float)
        arr = series.values
        for i in range(window, len(arr)):
            seg = arr[i - window : i]
            lags = np.array([2, 4, 8, 16])
            tau = []
            for lag in lags:
                if lag >= len(seg):
                    continue
                tau.append(np.std(seg[lag:] - seg[:-lag]))
            if len(tau) < 2:
                continue
            poly = np.polyfit(np.log(lags[: len(tau)]), np.log(np.maximum(tau, 1e-9)), 1)
            out[i] = poly[0]
        return pd.Series(out, index=series.index)

    def _cusum_break(self, series: pd.Series, window: int) -> pd.Series:
        ret = series.diff().fillna(0)
        s_pos = np.zeros(len(ret))
        s_neg = np.zeros(len(ret))
        thresh = ret.rolling(window, min_periods=max(5, window // 3)).std().fillna(ret.std()) * 2.5
        for i in range(1, len(ret)):
            s_pos[i] = max(0, s_pos[i - 1] + ret.iloc[i])
            s_neg[i] = min(0, s_neg[i - 1] + ret.iloc[i])
        return ((s_pos > thresh.values) | (np.abs(s_neg) > thresh.values)).astype(int)

    def _rolling_entropy(self, series: pd.Series, window: int) -> pd.Series:
        out = np.zeros(len(series), dtype=float)
        vals = series.values
        for i in range(window, len(vals)):
            seg = vals[i - window : i]
            hist, _ = np.histogram(seg, bins=10, density=True)
            p = hist / (hist.sum() + 1e-9)
            out[i] = -np.sum(p * np.log(p + 1e-9))
        return pd.Series(out, index=series.index)


class TripleBarrierLabeler:
    def __init__(self, cfg: dict):
        l = cfg["training"]["labeling"]
        self.cfg = BarrierConfig(pt_mult=float(l["pt_mult"]), sl_mult=float(l["sl_mult"]), max_holding_bars=int(l["max_holding_bars"]))

    def label(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["label"] = 2  # 0=short,1=long,2=no-trade

        atr = out["atr_14"].replace(0, np.nan).fillna(out["atr_14"].median())
        for i in range(len(out) - self.cfg.max_holding_bars - 1):
            entry = out.iloc[i]["close"]
            up = entry + self.cfg.pt_mult * atr.iloc[i]
            down = entry - self.cfg.sl_mult * atr.iloc[i]
            future = out.iloc[i + 1 : i + 1 + self.cfg.max_holding_bars]

            hit_up = (future["high"] >= up).idxmax() if (future["high"] >= up).any() else None
            hit_dn = (future["low"] <= down).idxmax() if (future["low"] <= down).any() else None

            if hit_up is not None and hit_dn is not None:
                out.at[i, "label"] = 1 if hit_up < hit_dn else 0
            elif hit_up is not None:
                out.at[i, "label"] = 1
            elif hit_dn is not None:
                out.at[i, "label"] = 0
            else:
                out.at[i, "label"] = 2

        return out


class InstitutionalModelStack:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.scaler = StandardScaler()
        self.tree = RandomForestClassifier(
            n_estimators=int(cfg["models"]["tree"]["n_estimators"]),
            max_depth=int(cfg["models"]["tree"]["max_depth"]),
            min_samples_leaf=int(cfg["models"]["tree"]["min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=13,
            n_jobs=-1,
        )
        self.temporal = LogisticRegression(max_iter=2000, multi_class="multinomial")
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.feature_cols: List[str] = []

    def fit(self, df: pd.DataFrame, feature_cols: List[str]):
        self.feature_cols = feature_cols
        x = df[feature_cols].values
        y = df["label"].values

        x = self.scaler.fit_transform(x)
        self.tree.fit(x, y)

        seq = self._temporal_embeddings(x)
        self.temporal.fit(seq, y)

        raw = self._ensemble_raw_probs(x)
        y_long = (y == 1).astype(int)
        self.calibrator.fit(raw[:, 1], y_long)

    def _temporal_embeddings(self, x: np.ndarray, lag: int = 16) -> np.ndarray:
        emb = np.zeros((x.shape[0], x.shape[1] * 3), dtype=float)
        for i in range(x.shape[0]):
            start = max(0, i - lag)
            seg = x[start : i + 1]
            emb[i, : x.shape[1]] = seg[-1]
            emb[i, x.shape[1] : 2 * x.shape[1]] = seg.mean(axis=0)
            emb[i, 2 * x.shape[1] :] = seg.std(axis=0)
        return emb

    def _ensemble_raw_probs(self, x: np.ndarray) -> np.ndarray:
        p_tree = self.tree.predict_proba(x)
        seq = self._temporal_embeddings(x)
        p_temp = self.temporal.predict_proba(seq)
        p = 0.55 * p_tree + 0.45 * p_temp
        p = p / p.sum(axis=1, keepdims=True)
        return p

    def predict_proba(self, latest_df: pd.DataFrame) -> Tuple[np.ndarray, float]:
        x = latest_df[self.feature_cols].values
        x = self.scaler.transform(x)
        p_raw = self._ensemble_raw_probs(x)

        p_long_cal = self.calibrator.transform(p_raw[:, 1])
        p_short = p_raw[:, 0]
        p_notrade = np.clip(1 - p_short - p_long_cal, 0, 1)
        p = np.vstack([p_short, p_long_cal, p_notrade]).T
        p = p / p.sum(axis=1, keepdims=True)

        uncertainty = float(np.mean(np.std(np.vstack([p_raw[:, 0], p_raw[:, 1], p_raw[:, 2]]), axis=0)))
        return p, uncertainty


class DecisionLayer:
    def __init__(self, cfg: dict):
        d = cfg["decision"]
        self.regime_thresholds = d["regime_thresholds"]
        self.max_uncertainty = float(d["max_uncertainty"])
        self.require_mtf_agreement = bool(d["require_mtf_agreement"])

    def apply(self, row: pd.Series, p: np.ndarray, uncertainty: float) -> Tuple[np.ndarray, str]:
        regime = str(row["regime_tag"])
        threshold = float(self.regime_thresholds.get(regime, self.regime_thresholds["default"]))

        p_short, p_long, p_notrade = float(p[0]), float(p[1]), float(p[2])
        reasons = []

        if uncertainty > self.max_uncertainty:
            p_notrade = max(p_notrade, 0.80)
            reasons.append("uncertainty")

        if regime in {"volatile_expansion", "low_vol_chop"}:
            p_notrade = max(p_notrade, 0.75)
            reasons.append("regime_block")

        if self.require_mtf_agreement:
            agree = abs(row.get("tf_1h_ret", 0) + row.get("tf_4h_ret", 0)) > 0.0001
            if not agree:
                p_notrade = max(p_notrade, 0.70)
                reasons.append("mtf_disagree")

        edge = max(p_short, p_long)
        if edge < threshold:
            p_notrade = max(p_notrade, 0.70)
            reasons.append("edge_low")

        pp = np.array([p_short, p_long, p_notrade], dtype=float)
        pp = pp / pp.sum()
        return pp, ",".join(reasons) if reasons else "ok"


class RiskIntelligenceEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        r = cfg["risk"]
        self.max_dd = float(r["max_drawdown"])
        self.max_consec_losses = int(r["max_consecutive_losses"])
        self.base_risk = float(r["base_risk_unit"])
        self.kelly_cap = float(r["kelly_cap"])
        self.dd_throttle = float(r["dd_throttle"])
        self.state = RiskState()

    def compute_multiplier(self, p_long: float, p_short: float, p_notrade: float, regime: str, uncertainty: float) -> float:
        edge = max(p_long, p_short) - 0.5
        kelly = np.clip(2 * edge, 0, self.kelly_cap)

        regime_scale = {
            "trend_expansion": 1.0,
            "structured_trend": 0.9,
            "range_compression": 0.6,
            "volatility_expansion": 0.45,
            "transitional": 0.5,
            "low_vol_chop": 0.35,
            "breakout_precondition": 0.7,
        }.get(regime, 0.5)

        uncertainty_scale = np.clip(1 - uncertainty * 2, 0.15, 1.0)
        notrade_scale = np.clip(1 - p_notrade, 0.0, 1.0)
        dd_scale = np.clip(1 - self.state.drawdown / max(self.max_dd, 1e-6), 0.0, 1.0)

        mult = kelly * regime_scale * uncertainty_scale * notrade_scale * dd_scale
        return float(np.clip(mult, 0, 1.0))

    def update_state(self, pnl: float):
        self.state.equity *= (1 + pnl)
        self.state.peak_equity = max(self.state.peak_equity, self.state.equity)
        self.state.drawdown = 1 - (self.state.equity / self.state.peak_equity)

        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0

        self.state.rolling_expectancy = 0.96 * self.state.rolling_expectancy + 0.04 * pnl

    def observation_mode(self) -> bool:
        if self.state.drawdown > self.max_dd * self.dd_throttle:
            return True
        if self.state.consecutive_losses >= self.max_consec_losses:
            return True
        if self.state.rolling_expectancy < 0:
            return True
        return False


class Backtester:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        b = cfg["backtest"]
        self.spread_bps = float(b["spread_bps"])
        self.slippage_bps = float(b["slippage_bps"])
        self.latency_bars = int(b["latency_bars"])

    def run(self, df: pd.DataFrame) -> Dict[str, float]:
        pnl = []
        for i in range(self.latency_bars, len(df) - 1):
            row = df.iloc[i]
            nxt = df.iloc[i + 1]
            pos = row["position"]
            if pos == 0:
                pnl.append(0.0)
                continue
            ret = (nxt["close"] - row["close"]) / row["close"]
            gross = ret * pos
            costs = (self.spread_bps + self.slippage_bps) / 10000.0
            pnl.append(gross - costs)

        pnl = np.array(pnl)
        eq = np.cumprod(1 + pnl)
        dd = 1 - eq / np.maximum.accumulate(eq)
        sharpe = np.mean(pnl) / (np.std(pnl) + 1e-9) * np.sqrt(252 * 24 * 60)
        sortino = np.mean(pnl) / (np.std(np.clip(pnl, None, 0)) + 1e-9) * np.sqrt(252 * 24 * 60)
        calmar = (eq[-1] - 1) / (dd.max() + 1e-9) if len(eq) else 0
        expectancy = np.mean(pnl)

        return {
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "calmar": float(calmar),
            "expectancy": float(expectancy),
            "max_drawdown": float(dd.max() if len(dd) else 0.0),
            "trades": int(np.sum(np.abs(df["position"].values) > 0)),
        }


def map_regime(cluster: int) -> str:
    mapping = {
        0: "structured_trend",
        1: "range_compression",
        2: "volatility_expansion",
        3: "trend_expansion",
        4: "transitional",
        5: "low_vol_chop",
    }
    return mapping.get(int(cluster), "transitional")


def build_feature_columns(df: pd.DataFrame) -> List[str]:
    skip = {"timestamp", "open", "high", "low", "close", "volume", "label", "position", "regime_tag"}
    cols = [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]
    return cols


def run_pipeline(cfg: dict, csv_path: str, output_path: str):
    data = DataArchitecture(cfg)
    raw = data.load_ohlcv(csv_path)
    clean = data.handle_missing_and_anomalies(raw)
    transformed = data.add_core_transforms(clean)
    mtf = data.build_multi_timeframe(transformed)

    feats = StructuralFeatureFactory(cfg).transform(mtf)
    feats["regime_tag"] = feats["regime_cluster"].apply(map_regime)

    labeled = TripleBarrierLabeler(cfg).label(feats)
    feature_cols = build_feature_columns(labeled)

    split = int(len(labeled) * cfg["training"]["train_ratio"])
    train_df = labeled.iloc[:split].copy()
    test_df = labeled.iloc[split:].copy()

    model = InstitutionalModelStack(cfg)
    model.fit(train_df, feature_cols)

    decision = DecisionLayer(cfg)
    risk = RiskIntelligenceEngine(cfg)

    positions = []
    outputs: List[DecisionOutput] = []

    probs, uncert = model.predict_proba(test_df)
    for idx, (i, row) in enumerate(test_df.iterrows()):
        p_adj, reason = decision.apply(row, probs[idx], uncert)
        p_short, p_long, p_no = float(p_adj[0]), float(p_adj[1]), float(p_adj[2])

        if p_no >= max(p_long, p_short):
            side = 0
            bias = "NO_TRADE"
        elif p_long > p_short:
            side = 1
            bias = "LONG"
        else:
            side = -1
            bias = "SHORT"

        mult = risk.compute_multiplier(p_long, p_short, p_no, str(row["regime_tag"]), uncert)
        if risk.observation_mode():
            side = 0
            mult = 0.0
            reason = f"observation_mode,{reason}"

        pos = side * mult
        positions.append(pos)

        conf_pct = float(np.percentile(probs[:, 1], p_long * 100)) if len(probs) else 0.0
        outputs.append(
            DecisionOutput(
                timestamp=str(row["timestamp"]),
                regime=str(row["regime_tag"]),
                structural_bias=bias,
                p_long=p_long,
                p_short=p_short,
                p_no_trade=p_no,
                uncertainty=float(uncert),
                risk_multiplier=float(mult),
                confidence_percentile=float(conf_pct),
                recommended_position_size=float(mult * cfg["risk"]["base_risk_unit"]),
            )
        )

    test_df["position"] = positions
    bt = Backtester(cfg).run(test_df)

    payload = {
        "metrics": bt,
        "decisions": [dataclasses.asdict(o) for o in outputs[-cfg["output"]["last_n_decisions"] :]],
    }

    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Institutional-grade market structure intelligence engine")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--input", required=True, help="Path to OHLCV CSV")
    p.add_argument("--output", default="engine_output.json")
    return p.parse_args()


def main():
    args = parse_args()
    with Path(args.config).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    payload = run_pipeline(cfg, args.input, args.output)
    print(json.dumps(payload["metrics"], indent=2))


if __name__ == "__main__":
    main()
