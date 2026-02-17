from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pyttsx3
import sounddevice as sd
from faster_whisper import WhisperModel
from pvrecorder import PvRecorder
import pvporcupine


@dataclass(slots=True)
class VoiceCommand:
    text: str
    timestamp: float
    is_interrupt: bool = False
    is_emergency: bool = False


class InterruptibleTTS:
    """Thread-safe, interruptible TTS wrapper around pyttsx3."""

    def __init__(self, rate: int = 180, volume: float = 1.0) -> None:
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True, name="tts-worker")
        self._worker.start()

    def speak_async(self, text: str) -> None:
        self._queue.put(text)

    def interrupt(self) -> None:
        self._stop_event.set()
        self._engine.stop()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        self._queue.put("")
        self._worker.join(timeout=2)
        self._engine.stop()

    def _run(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self._shutdown_event.is_set():
                break

            if not text:
                continue

            self._stop_event.clear()
            self._engine.say(text)
            self._engine.runAndWait()


class WakeWordListener:
    """Low-CPU wake-word listener using Porcupine + PvRecorder."""

    def __init__(
        self,
        access_key: str,
        wake_word: str = "jarvis",
        sensitivity: float = 0.65,
        sample_rate: int = 16000,
    ) -> None:
        self._porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=[wake_word],
            sensitivities=[sensitivity],
        )
        self._recorder = PvRecorder(device_index=-1, frame_length=self._porcupine.frame_length)
        self._sample_rate = sample_rate

    def listen_until_wake(self, stop_event: threading.Event) -> bool:
        self._recorder.start()
        try:
            while not stop_event.is_set():
                pcm = self._recorder.read()
                keyword_index = self._porcupine.process(pcm)
                if keyword_index >= 0:
                    return True
            return False
        finally:
            self._recorder.stop()

    def close(self) -> None:
        self._recorder.delete()
        self._porcupine.delete()


class StreamingSTT:
    """Captures mic audio and transcribes with faster-whisper."""

    def __init__(
        self,
        model_size: str = "base.en",
        sample_rate: int = 16000,
        silence_threshold: float = 0.015,
        max_record_seconds: int = 12,
    ) -> None:
        self._sample_rate = sample_rate
        self._silence_threshold = silence_threshold
        self._max_record_seconds = max_record_seconds
        self._model = WhisperModel(model_size, compute_type="int8", cpu_threads=4)

    def capture_and_transcribe(self) -> str:
        audio_chunks: list[np.ndarray] = []
        silence_frames = 0
        max_silence_frames = int(self._sample_rate * 1.0 / 1024)

        def callback(indata: np.ndarray, frames: int, _time, _status) -> None:
            nonlocal silence_frames
            mono = indata[:, 0].copy()
            audio_chunks.append(mono)
            rms = float(np.sqrt(np.mean(np.square(mono))))
            silence_frames = silence_frames + 1 if rms < self._silence_threshold else 0

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=callback,
        ):
            start = time.time()
            while time.time() - start < self._max_record_seconds:
                if silence_frames > max_silence_frames and len(audio_chunks) > 8:
                    break
                time.sleep(0.05)

        if not audio_chunks:
            return ""

        audio = np.concatenate(audio_chunks)
        segments, _ = self._model.transcribe(audio, language="en", vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()


class AudioEngine:
    """Coordinates wake-word, STT, interrupt phrases, and TTS."""

    def __init__(
        self,
        porcupine_access_key: str,
        wake_word: str = "jarvis",
        whisper_model: str = "base.en",
    ) -> None:
        self._stop_event = threading.Event()
        self._wake_listener = WakeWordListener(porcupine_access_key, wake_word=wake_word)
        self._stt = StreamingSTT(model_size=whisper_model)
        self.tts = InterruptibleTTS()
        self.on_command: Optional[Callable[[VoiceCommand], None]] = None

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="audio-engine").start()

    def stop(self) -> None:
        self._stop_event.set()
        self.tts.shutdown()
        self._wake_listener.close()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            woke = self._wake_listener.listen_until_wake(self._stop_event)
            if not woke:
                continue

            text = self._stt.capture_and_transcribe().lower().strip()
            if not text:
                continue

            is_interrupt = "jarvis stop" in text or text.strip() == "stop"
            is_emergency = "jarvis emergency stop" in text or "emergency stop" in text
            cmd = VoiceCommand(text=text, timestamp=time.time(), is_interrupt=is_interrupt, is_emergency=is_emergency)

            if self.on_command:
                self.on_command(cmd)

    def request_confirmation(self, prompt: str) -> bool:
        self.tts.speak_async(prompt)
        text = self._stt.capture_and_transcribe().lower().strip()
        return any(token in text for token in ["confirm", "yes", "proceed", "do it"])
