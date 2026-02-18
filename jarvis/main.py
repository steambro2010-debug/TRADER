from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from core.brain import ReasoningBrain
from core.memory import MemoryStore
from core.planner import Planner
from modules.voice import VoiceModule
from security.logger import setup_logger
from security.permissions import RiskEngine


class JarvisRuntime:
    def __init__(self, config_path: str) -> None:
        with open(config_path, "r", encoding="utf-8") as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        self.logger = setup_logger()
        self.memory = MemoryStore(
            self.config["memory"]["db_path"],
            self.config["memory"].get("retention_days", 30),
        )
        self.brain = ReasoningBrain(self.config, self.logger)
        self.planner = Planner(self.config, self.logger)
        self.voice = VoiceModule(self.config, self.logger)
        self.risk = RiskEngine(self.config)

    def process_text_command(self, text: str, confirmed: bool = False) -> Dict[str, Any]:
        if self.risk.is_emergency_stop(text):
            result = {
                "status": "ok",
                "message": "Emergency stop acknowledged. Halting active tasks.",
                "action": {
                    "intent": "emergency_stop",
                    "risk_level": "high",
                    "parameters": {},
                },
            }
            self.memory.log_action("emergency_stop", "high", {}, "ok", result["message"])
            return result

        action = self.brain.plan_action(text)
        result = self.planner.execute_action(action, confirmation=confirmed)
        self.memory.log_action(
            intent=result["action"]["intent"],
            risk_level=result["action"]["risk_level"],
            parameters=result["action"]["parameters"],
            status=result["status"],
            result=result["message"],
        )
        return result

    def run_continuous(self) -> None:
        self.logger.info("JARVIS runtime started. Listening for wake word...")
        while True:
            self.voice.wait_for_wake_word()
            self.voice.speak("Yes?")
            command = self.voice.listen_once(seconds=6)
            if not command:
                continue
            response = self.process_text_command(command.text)

            if response["status"] == "awaiting_confirmation":
                self.voice.speak(response["message"])
                confirm = self.voice.listen_once(seconds=5)
                is_yes = bool(confirm and any(k in confirm.text.lower() for k in ["yes", "confirm", "do it"]))
                if is_yes:
                    response = self.planner.execute_action(response["action"], confirmation=True)

            spoken = _concise_response(response)
            self.logger.info("JARVIS: %s", spoken)
            self.voice.speak(spoken)
            time.sleep(self.config["runtime"].get("loop_sleep_sec", 0.05))


def _concise_response(result: Dict[str, Any]) -> str:
    if result["status"] == "ok":
        return result["message"]
    if result["status"] == "awaiting_confirmation":
        return result["message"]
    return "Action failed. Check logs."


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS local assistant runtime")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", help="Run one text command and print JSON response")
    parser.add_argument("--confirmed", action="store_true", help="Mark command as user-confirmed")
    args = parser.parse_args()

    runtime = JarvisRuntime(args.config)
    if args.once:
        result = runtime.process_text_command(args.once, confirmed=args.confirmed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    runtime.run_continuous()


if __name__ == "__main__":
    main()
