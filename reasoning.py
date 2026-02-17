from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from control import DesktopController, ActionResult
from vision import ScreenState


@dataclass(slots=True)
class PlanStep:
    action: str
    args: dict[str, Any]


@dataclass(slots=True)
class ExecutionReport:
    ok: bool
    summary: str
    steps: list[str]


class ReasoningEngine:
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    def build_plan(self, utterance: str, screen: ScreenState | None = None) -> list[PlanStep]:
        text = utterance.lower()
        plan: list[PlanStep] = []

        if "what's on my screen" in text or "what is on my screen" in text:
            plan.append(PlanStep("describe_screen", {}))
            return plan

        if m := re.search(r"open (.+?) and search for (.+)", text):
            app, query = m.group(1), m.group(2)
            plan.extend(
                [
                    PlanStep("open_app", {"command": app}),
                    PlanStep("type_text", {"text": query}),
                    PlanStep("hotkey", {"keys": ["enter"]}),
                ]
            )
            return plan

        if "find my latest python project" in text:
            plan.append(PlanStep("search_files", {"root": "~", "query": "pyproject"}))
            return plan

        if m := re.search(r"search inside this code for (.+)", text):
            plan.append(
                PlanStep(
                    "search_text",
                    {"root": ".", "text": m.group(1).strip(), "extensions": [".py", ".md", ".txt", ".json"]},
                )
            )
            return plan

        if "close unnecessary apps" in text:
            plan.append(PlanStep("close_unnecessary", {}))
            return plan

        if "stop" in text:
            plan.append(PlanStep("stop", {}))
            return plan

        if "explain what this software does" in text:
            plan.append(PlanStep("describe_screen", {}))
            return plan

        # Generic fallback: open app or type
        if text.startswith("open "):
            plan.append(PlanStep("open_app", {"command": utterance[5:].strip()}))
            return plan

        plan.append(PlanStep("unknown", {"text": utterance, "screen": screen.to_dict() if screen else {}}))
        return plan

    def execute_plan(self, plan: list[PlanStep], screen: ScreenState | None = None) -> ExecutionReport:
        results: list[str] = []
        ok = True

        for step in plan:
            result = self._execute_step(step, screen)
            results.append(result.detail)
            ok = ok and result.success

        summary = " ; ".join(results) if results else "No actions executed"
        return ExecutionReport(ok=ok, summary=summary, steps=results)

    def _execute_step(self, step: PlanStep, screen: ScreenState | None) -> ActionResult:
        if step.action == "describe_screen":
            if not screen:
                return ActionResult(False, "No screen state available")
            msg = (
                f"Active app: {screen.active_app}. "
                f"I can see {len(screen.visible_text)} characters, "
                f"buttons: {', '.join(screen.detected_buttons[:5]) or 'none'}"
            )
            return ActionResult(True, msg)

        if step.action == "open_app":
            return self.controller.open_app(step.args["command"])
        if step.action == "type_text":
            return self.controller.type_text(step.args["text"])
        if step.action == "hotkey":
            return self.controller.hotkey(*step.args["keys"])
        if step.action == "search_files":
            matches = self.controller.search_files(step.args["root"], step.args["query"])
            detail = " | ".join(matches[:5]) if matches else "No matching files"
            return ActionResult(True, detail)
        if step.action == "search_text":
            matches = self.controller.search_text_in_files(
                step.args["root"], step.args["text"], step.args.get("extensions")
            )
            detail = f"Found {len(matches)} files containing '{step.args['text']}'"
            return ActionResult(True, detail)
        if step.action == "close_unnecessary":
            return self.controller.close_unnecessary_apps()
        if step.action == "stop":
            return ActionResult(True, "Stopping as requested")

        return ActionResult(False, f"Unknown instruction: {step.args.get('text', step.action)}")
