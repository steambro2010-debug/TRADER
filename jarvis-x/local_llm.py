"""Local LLM interface using Ollama."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import requests

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LocalLLM:
    base_url: str
    model: str
    timeout_s: int = 60

    def health_check(self) -> bool:
        """Return True when Ollama endpoint is reachable."""
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt: str) -> str:
        """Generate text using Ollama's /api/generate endpoint."""
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.RequestException as exc:
            LOGGER.exception("Local LLM request failed")
            return f"Local LLM unavailable: {exc}"
        except json.JSONDecodeError as exc:
            LOGGER.exception("Invalid JSON from Ollama")
            return f"Local LLM returned invalid data: {exc}"
