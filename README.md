# JARVIS Windows Voice Assistant (Production-Oriented Baseline)

A modular, voice-first desktop assistant for Windows 10/11 that can listen continuously, wake on **"Jarvis"**, execute desktop actions, analyze the active window, and respond with interruptible TTS.

## Features

- Always-on wake word detection (`pvporcupine` + `pvrecorder`)
- Low-latency local STT (`faster-whisper`)
- Interruptible TTS (`pyttsx3`), including immediate stop and emergency stop
- Desktop automation and process control (`pyautogui`, `pygetwindow`, `psutil`, subprocess)
- Active-window OCR vision loop (`mss`, `OpenCV`, `EasyOCR`)
- Step-by-step planning and execution with screen re-verification after each step
- Security gate with mandatory confirmation for high-risk actions
- Persistent local memory in SQLite for auditing and context

## Architecture Diagram (ASCII)

```text
 ┌─────────────────────────────────────────────────────────────────────┐
 │                          Audio Engine                               │
 │ Wake Word (Porcupine) -> Command Capture (Mic) -> STT (Whisper)    │
 └─────────────────────────────────────────────────────────────────────┘
                              │ VoiceCommand
                              v
┌────────────────────────────────────────────────────────────────────────────┐
│                                 Main Loop                                 │
│  Security Check -> Vision Scan -> Reasoning/Planning -> Action Execution  │
│                -> Post-step Vision Verify -> Memory Logging               │
└────────────────────────────────────────────────────────────────────────────┘
                              │ response text
                              v
                  ┌────────────────────────────┐
                  │   Interruptible TTS Out    │
                  └────────────────────────────┘

Modules:
- `audio_engine.py`
- `vision.py`
- `control.py`
- `reasoning.py`
- `security.py`
- `memory.py`
- `main.py`
```

## Setup (Windows, Python 3.11+)

1. Install Python 3.11+ and Git.
2. Create virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Set Porcupine access key:
   ```powershell
   setx PORCUPINE_ACCESS_KEY "<YOUR_KEY>"
   ```
5. Restart terminal and run:
   ```powershell
   python main.py
   ```

## Wake/Control Phrases

- "Jarvis" (wake word)
- "Jarvis stop" (interrupt current execution and speech)
- "Jarvis emergency stop" (hard stop on current automation)

## Command Coverage

Implemented command classes include:

- "Jarvis, what’s on my screen?"
- "Open Chrome and search for RTX 5090 specs"
- "Find my latest Python project"
- "Search inside this code for API"
- "Close unnecessary apps"
- "Explain what this software does"

The planner is extensible in `reasoning.py` for additional command grammars and plugin tools.

## Security Model

High-risk actions (delete/remove/registry/uninstall/kill-process/shutdown/reboot) require spoken confirmation.

Example confirmation spoken by assistant:

- "Jarvis is about to run a sensitive action ... Say confirm to continue."

## File Intelligence Notes

The controller includes:

- filename search (`search_files`)
- content search (`search_text_in_files`)

For production extension:

- PDF summarization (`pypdf`) in reasoning plugin
- folder watchers (`watchdog`) for proactive notifications
- indexed semantic retrieval over project/docs

## Advanced Mode (Design Roadmap)

1. **Multi-monitor support**
   - Capture and OCR all displays from `mss.monitors`
   - Maintain monitor-aware cursor/action transforms
2. **Autonomous background monitoring**
   - Rule engine over screen/process/file events
   - Scheduled and event-triggered actions
3. **Plugin system**
   - Signed plugin manifests with capability scopes
   - Async plugin bus and permission prompts per scope
4. **RL-assisted UI navigation**
   - Train policy over UI state/action logs
   - Safe policy constrained by security layer
5. **Tone-adaptive voice**
   - Sentiment/stress cues from text + prosody
   - Dynamic voice profile switching

## Operational Notes

- Run as standard user by default; elevate only for tasks requiring admin rights.
- Keep `pyautogui.FAILSAFE=True` (already enabled) to allow user abort by moving mouse to corner.
- For latency tuning, use a smaller/faster whisper model and CPU threading adjustments in `audio_engine.py`.
