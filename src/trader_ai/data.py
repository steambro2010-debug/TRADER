from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from .candle_extractor import Candle


class DataLogger:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.candles_path = self.base_dir / "candles.csv"
        self.signals_path = self.base_dir / "signals.csv"

    def append_candle(self, candle: Candle) -> None:
        self._append_row(self.candles_path, asdict(candle))

    def append_signal(self, row: dict[str, Any]) -> None:
        self._append_row(self.signals_path, row)

    def _append_row(self, path: Path, row: dict[str, Any]) -> None:
        df = pd.DataFrame([row])
        header = not path.exists()
        df.to_csv(path, mode="a", header=header, index=False)
