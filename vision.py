from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import cv2
import mss
import numpy as np
import pygetwindow as gw

try:
    import easyocr
except ImportError:  # fallback supported in production via requirements optional section
    easyocr = None


@dataclass(slots=True)
class ScreenState:
    active_app: str
    visible_text: str
    detected_buttons: list[str]
    input_fields: list[str]
    layout_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VisionEngine:
    def __init__(self) -> None:
        self._reader = easyocr.Reader(["en"], gpu=False) if easyocr else None

    def capture_active_window(self) -> np.ndarray:
        active = gw.getActiveWindow()
        if active is None:
            raise RuntimeError("No active window")

        bbox = {
            "left": active.left,
            "top": active.top,
            "width": max(active.width, 100),
            "height": max(active.height, 100),
        }
        with mss.mss() as sct:
            frame = np.array(sct.grab(bbox))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def analyze(self) -> ScreenState:
        active = gw.getActiveWindow()
        active_title = active.title if active else "Unknown"
        frame = self.capture_active_window()

        visible_text = ""
        buttons: list[str] = []
        input_fields: list[str] = []

        if self._reader:
            detections = self._reader.readtext(frame, detail=1, paragraph=False)
            texts = [det[1] for det in detections]
            visible_text = " ".join(texts)
            for t in texts:
                low = t.lower()
                if any(tok in low for tok in ["ok", "cancel", "submit", "save", "next"]):
                    buttons.append(t)
                if any(tok in low for tok in ["search", "email", "name", "password"]):
                    input_fields.append(t)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 90, 180)
        complexity = int(np.sum(edges > 0))
        layout_summary = f"Window '{active_title}' with OCR chars={len(visible_text)} edge_points={complexity}"

        return ScreenState(
            active_app=active_title,
            visible_text=visible_text[:4000],
            detected_buttons=list(dict.fromkeys(buttons)),
            input_fields=list(dict.fromkeys(input_fields)),
            layout_summary=layout_summary,
        )
