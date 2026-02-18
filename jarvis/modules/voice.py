from __future__ import annotations

import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import sounddevice as sd
from faster_whisper import WhisperModel
from TTS.api import TTS


@dataclass(slots=True)
class VoiceCommand:
    text: str
    confidence: float


class VoiceModule:
    """Continuous listening with wake-word gating and GPU STT/TTS."""

    def __init__(self, config: Dict[str, Any], logger) -> None:
        self.cfg = config
        self.logger = logger
        whisper_cfg = config["models"]["whisper"]
        self.whisper = WhisperModel(
            whisper_cfg["size"],
            device=whisper_cfg.get("device", "cuda"),
            compute_type=whisper_cfg.get("compute_type", "float16"),
        )
        tts_cfg = config["models"]["tts"]
        self.tts = TTS(model_name=tts_cfg["model_name"], gpu=tts_cfg.get("use_cuda", True))
        self.sample_rate = 16000

    def speak(self, text: str) -> None:
        out = Path("logs") / "last_response.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.tts.tts_to_file(text=text, file_path=str(out))

    def listen_once(self, seconds: int = 4) -> Optional[VoiceCommand]:
        recording = sd.rec(int(seconds * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype="int16")
        sd.wait()
        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp_wav.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())

        segments, info = self.whisper.transcribe(tmp_wav.name, beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            return None
        return VoiceCommand(text=text, confidence=float(getattr(info, "language_probability", 0.7)))

    def wait_for_wake_word(self) -> VoiceCommand:
        wake = self.cfg["assistant"]["wake_word"].lower()
        while True:
            cmd = self.listen_once(seconds=self.cfg["runtime"]["wake_timeout_sec"])
            if cmd and wake in cmd.text.lower():
                return cmd
