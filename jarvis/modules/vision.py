from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import mss
import mss.tools
import pytesseract


class VisionModule:
    def __init__(self, config: Dict[str, Any], logger) -> None:
        self.config = config
        self.logger = logger
        tesseract_cmd = config["runtime"].get("tesseract_cmd")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def _capture(self) -> Path:
        out_dir = Path(self.config["runtime"]["screenshot_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        full_path = out_dir / filename
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            mss.tools.to_png(shot.rgb, shot.size, output=str(full_path))
        return full_path

    def execute(self, intent: str, params: Dict[str, Any]) -> str:
        if intent in {"summarize_screen", "analyze_screen_next_step", "take_screenshot"}:
            image_path = self._capture()
            text = pytesseract.image_to_string(str(image_path))
            compact = " ".join(text.split())[:800]
            if intent == "take_screenshot":
                return f"Screenshot saved to {image_path}"
            if intent == "summarize_screen":
                return f"Screen snapshot captured. OCR summary: {compact or 'No readable text found.'}"
            return (
                "Screenshot captured. OCR notes: "
                f"{compact or 'No readable text found.'}. "
                "Suggested next step: open the most prominent actionable button or menu shown."
            )
        raise ValueError(f"Unsupported vision intent: {intent}")
