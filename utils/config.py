from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json


CONFIG_PATH = Path("config.json")


@dataclass
class RiskConfig:
    capital_pct: float = 0.02
    martingale_enabled: bool = False
    martingale_multiplier: float = 2.0
    stop_loss_streak_limit: int = 3
    max_trades_per_hour: int = 12


@dataclass
class RuntimeConfig:
    quotex_url: str = "https://quotex.com/en"
    capture_fps: int = 15
    min_confidence: float = 75.0
    history_size: int = 500
    auto_trade_enabled: bool = False
    debug: bool = True
    region: tuple[int, int, int, int] | None = None


@dataclass
class AppConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    raw = json.loads(path.read_text())
    runtime = RuntimeConfig(**raw.get("runtime", {}))
    risk = RiskConfig(**raw.get("risk", {}))
    return AppConfig(runtime=runtime, risk=risk)


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(asdict(config), indent=2))
