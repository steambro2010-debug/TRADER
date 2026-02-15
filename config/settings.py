from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class Settings:
    raw: Dict[str, Any]

    @property
    def debug(self) -> bool:
        return bool(self.raw.get("debug", {}).get("enabled", False))


def load_settings(config_path: str) -> Settings:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Settings(raw=data)
