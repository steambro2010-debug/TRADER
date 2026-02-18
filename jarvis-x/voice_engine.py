"""Voice input/output engine.

Implements wake-word based command extraction and TTS output.
Speech recognition runs in a background loop when dependencies/devices exist.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable

import pyttsx3

try:
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model
except Exception:  # Optional dependencies in constrained environments.
    sd = None
    KaldiRecognizer = None
    Model = None

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class VoiceEngine:
    wake_word: str
    vosk_model_path: str

    def __post_init__(self) -> None:
        self._tts = pyttsx3.init()
        self._tts_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=20)
        self._listener_thread: threading.Thread | None = None
        self._recognizer = None

    def speak(self, text: str) -> None:
        """Speak text synchronously but thread-safe and interruptible."""
        with self._tts_lock:
            self._tts.stop()
            self._tts.say(text)
            self._tts.runAndWait()

    def stop_speaking(self) -> None:
        with self._tts_lock:
            self._tts.stop()

    def _audio_callback(self, indata, frames, time, status) -> None:  # type: ignore[no-untyped-def]
        if status:
            LOGGER.warning("Audio status: %s", status)
        if not self._audio_queue.full():
            self._audio_queue.put(bytes(indata))

    def start_listening(self, on_command: Callable[[str], None]) -> bool:
        """Start non-blocking listener thread with wake word parsing."""
        if sd is None or Model is None:
            LOGGER.warning("Vosk/sounddevice unavailable; skipping microphone listener.")
            return False

        if self._listener_thread and self._listener_thread.is_alive():
            return True

        def _loop() -> None:
            try:
                model = Model(self.vosk_model_path)
                self._recognizer = KaldiRecognizer(model, 16000)
                with sd.RawInputStream(
                    samplerate=16000,
                    blocksize=8000,
                    dtype="int16",
                    channels=1,
                    callback=self._audio_callback,
                ):
                    LOGGER.info("Voice listener started")
                    while not self._stop_event.is_set():
                        try:
                            data = self._audio_queue.get(timeout=1)
                        except queue.Empty:
                            continue
                        if self._recognizer.AcceptWaveform(data):
                            result = json.loads(self._recognizer.Result())
                            text = (result.get("text") or "").strip().lower()
                            command = self._parse_command(text)
                            if command:
                                on_command(command)
            except Exception:
                LOGGER.exception("Voice listener crashed")

        self._stop_event.clear()
        try:
            self._listener_thread = threading.Thread(target=_loop, name="VoiceListener", daemon=True)
            self._listener_thread.start()
        except Exception:
            LOGGER.exception("Failed to start voice listener thread")
            return False
        return True

    def _parse_command(self, text: str) -> str | None:
        """Return command body after wake word, or None."""
        if not text:
            return None
        if text.startswith(self.wake_word):
            return text[len(self.wake_word) :].strip()
        if f"{self.wake_word} " in text:
            return text.split(f"{self.wake_word} ", 1)[1].strip()
        return None

    def stop(self) -> None:
        self._stop_event.set()
        self.stop_speaking()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2)
