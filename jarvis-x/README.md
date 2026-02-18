# JARVIS-X (Phase 1 MVP)

Production-oriented scaffold for a local, modular AI desktop assistant on Windows 11.

## Implemented in Phase 1
- Voice engine skeleton with wake-word command parsing (`jarvis`).
- Text-to-speech via `pyttsx3`.
- Local LLM integration via Ollama.
- Central planner with simple complexity routing to local model vs ChatGPT bridge stub.
- SQLite memory for command history and preferences.

## Project Structure
See required module layout in this folder (`main.py`, `planner.py`, `voice_engine.py`, etc.).

## Setup (Windows 11)
1. Open Command Prompt in `jarvis-x`.
2. Run:
   ```bat
   setup.bat
   ```
3. Ensure Ollama is running and pull a lightweight model:
   ```powershell
   ollama pull tinyllama
   ```
4. Download a Vosk English model and extract it to:
   `models\vosk-model-small-en-us-0.15`
5. Start the assistant:
   ```powershell
   python main.py
   ```

## Usage
- Speak (or type fallback) commands prefixed by wake word:
  - `jarvis open chrome`
  - `jarvis research nvidia and give detailed report`
- Type `exit` to quit text fallback mode.

## Notes
- Browser automation, messaging workflows, UI panel, and screen vision are scaffolded for later phases.
- ChatGPT browser automation is intentionally not using OpenAI API keys.
