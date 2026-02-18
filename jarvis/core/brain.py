from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
except Exception:  # runtime fallback
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    BitsAndBytesConfig = None


SYSTEM_PROMPT = """You are JARVIS planner. Return ONLY strict JSON with schema:
{
  \"intent\": string,
  \"risk_level\": \"low\"|\"medium\"|\"high\",
  \"parameters\": object
}
No markdown. No commentary. No additional keys.
"""


class ReasoningBrain:
    def __init__(self, config: Dict[str, Any], logger) -> None:
        self.cfg = config["models"]["llm"]
        self.logger = logger
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self) -> None:
        model_path = self.cfg["path"]
        if not AutoTokenizer or not AutoModelForCausalLM:
            self.logger.warning("Transformers not available; using fallback parser.")
            return
        if not Path(model_path).exists():
            self.logger.warning("LLM path %s missing; using fallback parser.", model_path)
            return

        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            quantization_config=quant_cfg,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        self.logger.info("Reasoning model loaded from %s", model_path)

    def plan_action(self, command_text: str) -> Dict[str, Any]:
        if not self.model or not self.tokenizer:
            return self._fallback_plan(command_text)

        prompt = (
            f"{SYSTEM_PROMPT}\n"
            f"User command: {command_text}\n"
            "Return JSON now."
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            do_sample=True,
            temperature=self.cfg.get("temperature", 0.2),
            top_p=self.cfg.get("top_p", 0.9),
            max_new_tokens=self.cfg.get("max_new_tokens", 220),
        )
        decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        json_text = decoded.rsplit("Return JSON now.", 1)[-1].strip()

        try:
            action = json.loads(json_text)
            return self._validate_action(action)
        except Exception:
            self.logger.exception("Model returned invalid JSON. Falling back.")
            return self._fallback_plan(command_text)

    def _validate_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if "intent" not in action or "risk_level" not in action or "parameters" not in action:
            raise ValueError("Missing required keys")
        return {
            "intent": str(action["intent"]),
            "risk_level": str(action["risk_level"]).lower(),
            "parameters": dict(action["parameters"]),
        }

    def _fallback_plan(self, command_text: str) -> Dict[str, Any]:
        txt = command_text.lower()
        if txt.startswith("open "):
            return {
                "intent": "open_app",
                "risk_level": "low",
                "parameters": {"app_name": command_text[5:].strip()},
            }
        if "screenshot" in txt and "next step" in txt:
            return {
                "intent": "analyze_screen_next_step",
                "risk_level": "low",
                "parameters": {},
            }
        if "what's on my screen" in txt or "what is on my screen" in txt:
            return {
                "intent": "summarize_screen",
                "risk_level": "low",
                "parameters": {},
            }
        return {
            "intent": "research_query",
            "risk_level": "medium",
            "parameters": {"query": command_text},
        }
