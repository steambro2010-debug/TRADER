"""Central planner for routing intents and orchestrating modules."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from gpt_bridge import GPTBridge
from local_llm import LocalLLM
from memory import MemoryStore

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Planner:
    local_llm: LocalLLM
    gpt_bridge: GPTBridge
    memory: MemoryStore

    def handle_command(self, command: str) -> str:
        """Phase 1 command handling with basic complexity routing."""
        cleaned = command.strip()
        self.memory.add_command(cleaned)

        if not cleaned:
            return "I didn't catch that command."

        if self._is_complex(cleaned):
            LOGGER.info("Complex task detected, routing to ChatGPT browser bridge")
            return self.gpt_bridge.ask_chatgpt_via_browser(cleaned)

        prompt = (
            "You are JARVIS-X, a concise desktop assistant. "
            "Answer the user's command clearly.\n\n"
            f"User command: {cleaned}"
        )
        return self.local_llm.generate(prompt)

    @staticmethod
    def _is_complex(command: str) -> bool:
        triggers = (
            "research",
            "detailed report",
            "strategy",
            "plan",
            "create document",
            "code",
            "compare",
            "multi-step",
        )
        return any(token in command.lower() for token in triggers)
