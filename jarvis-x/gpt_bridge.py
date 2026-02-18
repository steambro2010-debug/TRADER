"""Browser ChatGPT bridge scaffold.

Phase 1: placeholder interface for Phase 2 browser automation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GPTBridge:
    def ask_chatgpt_via_browser(self, prompt: str) -> str:
        """Placeholder for Playwright/Selenium-based ChatGPT automation."""
        return (
            "ChatGPT browser bridge is not implemented in Phase 1. "
            "Use local LLM for now."
        )
