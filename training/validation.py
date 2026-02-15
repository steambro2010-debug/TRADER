from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit


def walk_forward_splits(df: pd.DataFrame, n_splits: int = 4):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    idx = np.arange(len(df))
    for tr, te in tscv.split(idx):
        yield tr, te
