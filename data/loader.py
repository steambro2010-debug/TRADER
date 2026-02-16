from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


PLACEHOLDER_INPUTS = {
    "your_ohlcv.csv",
    "path/to/your_real_ohlcv.csv",
    "path/to/data.csv",
}


def resolve_input_path(csv_path: str) -> Path:
    p = Path(csv_path)
    if p.exists():
        return p
    normalized = csv_path.replace('\\', '/').lower().strip()
    if normalized in PLACEHOLDER_INPUTS:
        files = sorted(Path.cwd().glob("*.csv"))
        if len(files) == 1:
            return files[0]
    return p


def load_ohlcv(csv_path: str) -> pd.DataFrame:
    path = resolve_input_path(csv_path)
    if not path.exists():
        csv_candidates = sorted(Path.cwd().glob("*.csv"))
        candidate_hint = "\n".join(f"  - {p.name}" for p in csv_candidates) or "  (none)"
        raise FileNotFoundError(
            "Input file not found: "
            f"{csv_path}\n"
            "You likely used a README placeholder path. Use one of these options:\n"
            "1) Generate sample data: python main.py --example-csv\n"
            "2) Re-run with a real file: python main.py --config config.yaml --input <your_file.csv> --output engine_output.json\n"
            "CSV files detected in current directory:\n"
            f"{candidate_hint}"
        )
    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def preprocess(df: pd.DataFrame, base_freq: str) -> pd.DataFrame:
    out = df.set_index("timestamp")
    idx = pd.date_range(out.index.min(), out.index.max(), freq=base_freq, tz="UTC")
    out = out.reindex(idx)
    out.index.name = "timestamp"

    ret = np.log(out["close"]).diff()
    vol = ret.rolling(30, min_periods=5).std().fillna(ret.std())
    for col in ["open", "high", "low", "close", "volume"]:
        interp = out[col].interpolate(method="time", limit_direction="both")
        out[col] = np.where(out[col].isna(), interp, out[col])
    out["missing_flag"] = out[["open", "high", "low", "close"]].isna().any(axis=1).astype(int)
    out["log_return"] = np.log(out["close"]).diff().fillna(0)
    out["vol_norm_return"] = out["log_return"] / (vol.replace(0, np.nan)).fillna(0)
    out["detrended_close"] = out["close"] - out["close"].rolling(100, min_periods=10).mean()
    return out.reset_index().fillna(0)


def aggregate_timeframes(df: pd.DataFrame, timeframes: list[str]) -> Dict[str, pd.DataFrame]:
    base = df.set_index("timestamp")
    frames: Dict[str, pd.DataFrame] = {"1x": df.copy()}
    mapping = {"3x": "3T", "5x": "5T", "15x": "15T", "1h": "1H", "4h": "4H"}
    for tf in timeframes:
        if tf == "1x":
            continue
        rule = mapping[tf]
        agg = base.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()
        agg["log_return"] = np.log(agg["close"]).diff().fillna(0)
        frames[tf] = agg
    return frames
