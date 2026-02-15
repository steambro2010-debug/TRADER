import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "quotex_url": "https://qxbroker.com/en/sign-in",
    "region": None,
    "min_candles_required": 200,
    "prediction_interval": 5,
    "confidence_threshold": 0.60,
    "fps_cap": 12,
    "candle_duration_sec": 60,
    "x_shift_threshold": 7.5,
    "model_path": "models/latest.pkl",
    "browser_profile_dir": ".browser_profile",
    "security_timeout_sec": 240,
}


class ConfigManager:
    def __init__(self, path: str = "config.json") -> None:
        self.path = Path(path)
        self._lock = RLock()
        self._config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(loaded)
                self._config = merged
            else:
                self._config = DEFAULT_CONFIG.copy()
                self.save()
            return self._config.copy()

    def save(self) -> None:
        with self._lock:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._config[key] = value
            self.save()

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return self._config.copy()
