from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class SecurityDecision:
    allowed: bool
    reason: str


class SecurityLayer:
    HIGH_RISK_KEYWORDS = {
        "delete",
        "remove",
        "format",
        "registry",
        "uninstall",
        "kill process",
        "shutdown",
        "reboot",
    }

    def __init__(self, confirm_callback: Callable[[str], bool]) -> None:
        self._confirm_callback = confirm_callback

    def evaluate(self, intent_text: str) -> SecurityDecision:
        text = intent_text.lower()
        risky = any(kw in text for kw in self.HIGH_RISK_KEYWORDS)
        if not risky:
            return SecurityDecision(True, "Non-risky action")

        prompt = f"Jarvis is about to run a sensitive action: {intent_text}. Say confirm to continue."
        confirmed = self._confirm_callback(prompt)
        if confirmed:
            return SecurityDecision(True, "User confirmed sensitive action")
        return SecurityDecision(False, "User denied sensitive action")
