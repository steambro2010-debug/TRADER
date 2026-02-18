from __future__ import annotations

import subprocess
from typing import Any, Dict

import pyautogui


class DesktopModule:
    def __init__(self, config: Dict[str, Any], logger) -> None:
        self.config = config
        self.logger = logger

    def execute(self, intent: str, params: Dict[str, Any]) -> str:
        if intent == "open_app":
            app_name = params["app_name"].strip().lower()
            path = self.config["runtime"]["app_launch_paths"].get(app_name)
            target = path if path else params["app_name"]
            subprocess.Popen(target)
            return f"Opening {params['app_name']}."

        if intent == "hotkey":
            keys = params["keys"]
            pyautogui.hotkey(*keys)
            return "Hotkey executed."

        if intent == "type_text":
            pyautogui.write(params["text"], interval=0.01)
            return "Typed text."

        raise ValueError(f"Unsupported desktop intent: {intent}")
