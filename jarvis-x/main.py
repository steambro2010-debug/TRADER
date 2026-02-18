"""JARVIS-X entrypoint.

Phase 1 implements:
- Voice engine startup
- Local LLM integration via Ollama
- Wake-word command parsing
- Basic planner routing
"""
from __future__ import annotations

import logging
import threading
import time

from config import CONFIG
from gpt_bridge import GPTBridge
from local_llm import LocalLLM
from memory import MemoryStore
from planner import Planner
from voice_engine import VoiceEngine


def setup_logging() -> None:
    CONFIG.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, CONFIG.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(CONFIG.log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def run_text_fallback(planner: Planner, voice: VoiceEngine) -> None:
    """Fallback loop when microphone stack is unavailable."""
    print("Microphone listener unavailable. Type commands prefixed with wake word (e.g. 'jarvis hello').")
    while True:
        raw = input("> ").strip()
        if raw.lower() in {"exit", "quit"}:
            break
        cmd = voice._parse_command(raw.lower())
        if not cmd:
            continue
        response = planner.handle_command(cmd)
        print(response)
        voice.speak(response)


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    CONFIG.data_dir.mkdir(parents=True, exist_ok=True)
    memory = MemoryStore(CONFIG.data_dir / "jarvis.db")
    local_llm = LocalLLM(CONFIG.ollama_base_url, CONFIG.ollama_model)
    if not local_llm.health_check():
        logger.warning("Ollama health check failed at %s. Local LLM requests may fail.", CONFIG.ollama_base_url)

    bridge = GPTBridge()
    planner = Planner(local_llm=local_llm, gpt_bridge=bridge, memory=memory)
    voice = VoiceEngine(CONFIG.wake_word, str(CONFIG.vosk_model_path))
    execution_lock = threading.Lock()

    def on_command(command: str) -> None:
        if not execution_lock.acquire(blocking=False):
            logger.info("Command ignored while previous command is still executing")
            return
        try:
            logger.info("Command received: %s", command)
            response = planner.handle_command(command)
            logger.info("Response: %s", response)
            voice.speak(response)
        finally:
            execution_lock.release()

    try:
        listener_started = voice.start_listening(on_command)
        if listener_started:
            while True:
                time.sleep(0.5)
        else:
            run_text_fallback(planner, voice)
    except KeyboardInterrupt:
        logger.info("Shutting down JARVIS-X")
    finally:
        voice.stop()


if __name__ == "__main__":
    main()
