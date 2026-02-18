"""Central configuration for JARVIS-X.

Phase 1 focuses on voice I/O, local LLM routing, and basic planning.
All settings are environment-overridable and Windows-friendly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    app_name: str = "JARVIS-X"
    wake_word: str = os.getenv("JARVIS_WAKE_WORD", "jarvis")
    log_level: str = os.getenv("JARVIS_LOG_LEVEL", "INFO")

    # Vosk model path (downloaded separately).
    vosk_model_path: Path = Path(os.getenv("JARVIS_VOSK_MODEL", "models/vosk-model-small-en-us-0.15"))

    # Local LLM via Ollama.
    ollama_model: str = os.getenv("JARVIS_OLLAMA_MODEL", "tinyllama")
    ollama_base_url: str = os.getenv("JARVIS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    # Runtime behavior.
    command_timeout_s: int = int(os.getenv("JARVIS_COMMAND_TIMEOUT_S", "10"))
    enable_voice_loop: bool = os.getenv("JARVIS_ENABLE_VOICE_LOOP", "1") == "1"

    # Storage.
    data_dir: Path = Path(os.getenv("JARVIS_DATA_DIR", "data"))
    log_file: Path = Path(os.getenv("JARVIS_LOG_FILE", "logs/jarvis.log"))


CONFIG = AppConfig()
