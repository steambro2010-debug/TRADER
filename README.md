# JARVIS Windows Voice Assistant (Production-Oriented Baseline)

A modular, voice-first desktop assistant for Windows 10/11 that can listen continuously, wake on **"Jarvis"**, execute desktop actions, analyze the active window, and respond with interruptible TTS.

## Features

- Always-on wake detection with:
  - **Porcupine mode** (if `PORCUPINE_ACCESS_KEY` is set)
  - **No-key Whisper fallback mode** (works without Porcupine key)
- Local STT (`faster-whisper`)
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
 │ Wake detect (Porcupine OR Whisper fallback) -> STT (Whisper)        │
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
4. (Optional) Enable Porcupine wake mode by setting your key:
   ```powershell
   setx PORCUPINE_ACCESS_KEY "<YOUR_KEY>"
   ```
   If omitted, Jarvis still runs in no-key wake mode using short rolling Whisper captures.
5. Restart terminal and run:
   ```powershell
   python main.py
   ```

## Wake/Control Phrases

- "Jarvis" (wake word)
- "Jarvis stop" (interrupt current execution and speech)
- "Jarvis emergency stop" (hard stop on current automation)

## Security Model

High-risk actions (delete/remove/registry/uninstall/kill-process/shutdown/reboot) require spoken confirmation.

## Operational Notes

- Run as standard user by default; elevate only for tasks requiring admin rights.
- Keep `pyautogui.FAILSAFE=True` (already enabled) to allow user abort by moving mouse to corner.
- For lower latency in no-key mode, use a smaller Whisper model and tune recording limits in `audio_engine.py`.
