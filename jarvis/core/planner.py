from __future__ import annotations

import json
from typing import Any, Dict, Callable

from modules.browser import BrowserModule
from modules.desktop import DesktopModule
from modules.filesystem import FilesystemModule
from modules.messaging import MessagingModule
from modules.vision import VisionModule
from security.permissions import RiskEngine


class Planner:
    """Tool-only execution planner. No free-form side effects allowed."""

    def __init__(self, config: Dict[str, Any], logger) -> None:
        self.config = config
        self.logger = logger
        self.risk = RiskEngine(config)

        self.desktop = DesktopModule(config, logger)
        self.filesystem = FilesystemModule()
        self.vision = VisionModule(config, logger)
        self.browser = BrowserModule(config)
        self.messaging = MessagingModule()

        self.routes: Dict[str, Callable[[str, Dict[str, Any]], str]] = {
            "open_app": self.desktop.execute,
            "hotkey": self.desktop.execute,
            "type_text": self.desktop.execute,
            "create_folder": self.filesystem.execute,
            "create_file": self.filesystem.execute,
            "move_file": self.filesystem.execute,
            "rename_file": self.filesystem.execute,
            "delete_path": self.filesystem.execute,
            "take_screenshot": self.vision.execute,
            "summarize_screen": self.vision.execute,
            "analyze_screen_next_step": self.vision.execute,
            "research_query": self.browser.execute,
            "browser_search": self.browser.execute,
            "send_message": self.messaging.execute,
            "send_external_message": self.messaging.execute,
        }

    def normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if not {"intent", "risk_level", "parameters"}.issubset(action):
            raise ValueError("Invalid action schema")
        intent = action["intent"]
        inferred_risk = self.risk.classify_intent(intent)
        requested_risk = action["risk_level"].lower()
        risk_level = inferred_risk if inferred_risk != "low" else requested_risk
        normalized = {
            "intent": intent,
            "risk_level": risk_level,
            "parameters": dict(action["parameters"]),
        }
        self.logger.info("Planned action: %s", json.dumps(normalized, ensure_ascii=False))
        return normalized

    def execute_action(self, action: Dict[str, Any], confirmation: bool = False) -> Dict[str, Any]:
        action = self.normalize_action(action)
        decision = self.risk.check(action)
        if decision.requires_confirmation and not confirmation:
            return {
                "status": "awaiting_confirmation",
                "message": decision.message,
                "action": action,
            }

        intent = action["intent"]
        if intent not in self.routes:
            return {
                "status": "error",
                "message": f"No tool route for intent '{intent}'",
                "action": action,
            }

        try:
            result = self.routes[intent](intent, action["parameters"])
            return {
                "status": "ok",
                "message": result,
                "action": action,
            }
        except Exception as exc:
            self.logger.exception("Execution failed for intent=%s", intent)
            return {
                "status": "error",
                "message": str(exc),
                "action": action,
            }
