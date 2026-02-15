from pathlib import Path
from typing import Any, Optional


class ModelLoader:
    def __init__(self, model_path: str, logger) -> None:
        self.model_path = Path(model_path)
        self.logger = logger

    def load(self) -> Optional[Any]:
        if not self.model_path.exists():
            self.logger.warning("Model file not found at %s, using heuristic predictor mode.", self.model_path)
            return None
        try:
            import joblib

            model = joblib.load(self.model_path)
            self.logger.info("Loaded model from %s", self.model_path)
            return model
        except Exception as exc:
            self.logger.error("Failed to load model, using heuristic mode: %s", exc)
            return None
