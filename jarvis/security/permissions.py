from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(slots=True)
class PermissionDecision:
    allowed: bool
    requires_confirmation: bool
    message: str


class RiskEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.medium_intents = set(config["safety"]["confirm_intents"]["medium"])
        self.high_intents = set(config["safety"]["confirm_intents"]["high"])
        self.stop_phrases = {p.strip().lower() for p in config["safety"]["emergency_stop_phrases"]}

    def classify_intent(self, intent: str) -> str:
        if intent in self.high_intents:
            return "high"
        if intent in self.medium_intents:
            return "medium"
        return "low"

    def is_emergency_stop(self, text: str) -> bool:
        return text.strip().lower() in self.stop_phrases

    def check(self, action: Dict[str, Any]) -> PermissionDecision:
        risk_level = action["risk_level"].lower()
        if risk_level == "high":
            return PermissionDecision(
                allowed=True,
                requires_confirmation=True,
                message="This is a high-risk action. Explicit confirmation required.",
            )
        if risk_level == "medium":
            return PermissionDecision(
                allowed=True,
                requires_confirmation=True,
                message="Confirm this action.",
            )
        return PermissionDecision(
            allowed=True,
            requires_confirmation=False,
            message="Auto-approved.",
        )
