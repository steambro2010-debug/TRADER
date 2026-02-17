from __future__ import annotations

import os
import queue
import signal
import threading
import time

from audio_engine import AudioEngine, VoiceCommand
from control import DesktopController
from memory import MemoryStore
from reasoning import ReasoningEngine
from security import SecurityLayer
from vision import VisionEngine


class JarvisAssistant:
    def __init__(self) -> None:
        key = os.getenv("PORCUPINE_ACCESS_KEY", "")
        if not key:
            raise RuntimeError("Set PORCUPINE_ACCESS_KEY in environment")

        self.audio = AudioEngine(porcupine_access_key=key, wake_word="jarvis", whisper_model="base.en")
        self.controller = DesktopController()
        self.vision = VisionEngine()
        self.memory = MemoryStore()
        self.reasoning = ReasoningEngine(self.controller)
        self.security = SecurityLayer(confirm_callback=self.audio.request_confirmation)

        self.command_queue: queue.Queue[VoiceCommand] = queue.Queue()
        self.shutdown_event = threading.Event()
        self.action_cancel_event = threading.Event()

        self.audio.on_command = self._on_voice_command

    def _on_voice_command(self, cmd: VoiceCommand) -> None:
        self.command_queue.put(cmd)

    def run(self) -> None:
        self.audio.tts.speak_async("Jarvis online. Listening for wake word.")
        self.audio.start()

        while not self.shutdown_event.is_set():
            try:
                cmd = self.command_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if cmd.is_emergency:
                self._emergency_stop()
                continue

            if cmd.is_interrupt:
                self._interrupt_current_work()
                continue

            self._execute_command(cmd)

    def _execute_command(self, cmd: VoiceCommand) -> None:
        self.memory.add_event("utterance", {"text": cmd.text, "ts": cmd.timestamp})

        decision = self.security.evaluate(cmd.text)
        self.memory.add_event("security", {"allowed": decision.allowed, "reason": decision.reason})
        if not decision.allowed:
            self.audio.tts.speak_async("Action cancelled for safety.")
            return

        self.action_cancel_event.clear()
        screen = None
        try:
            screen = self.vision.analyze()
            self.memory.add_event("screen", screen.to_dict())
        except Exception as exc:
            self.memory.add_event("screen_error", {"error": str(exc)})

        plan = self.reasoning.build_plan(cmd.text, screen)
        self.memory.add_event("plan", {"steps": [s.action for s in plan]})

        for idx, step in enumerate(plan, start=1):
            if self.action_cancel_event.is_set() or self.shutdown_event.is_set():
                self.audio.tts.interrupt()
                self.memory.add_event("cancelled", {"step": step.action})
                return

            report = self.reasoning.execute_plan([step], screen)
            self.memory.add_event(
                "step_result",
                {"step": step.action, "ok": report.ok, "summary": report.summary, "index": idx},
            )

            self.audio.tts.speak_async(report.summary)

            # Re-scan after each step to adapt to UI changes.
            try:
                screen = self.vision.analyze()
                self.memory.add_event("screen_after_step", screen.to_dict())
            except Exception as exc:
                self.memory.add_event("screen_after_step_error", {"error": str(exc), "step": step.action})

            time.sleep(0.1)

    def _interrupt_current_work(self) -> None:
        self.action_cancel_event.set()
        self.audio.tts.interrupt()
        self.memory.add_event("interrupt", {"reason": "user stop"})

    def _emergency_stop(self) -> None:
        self.action_cancel_event.set()
        self.audio.tts.interrupt()
        self.memory.add_event("emergency_stop", {"ts": time.time()})
        self.audio.tts.speak_async("Emergency stop activated. Waiting for next command.")

    def shutdown(self) -> None:
        self.shutdown_event.set()
        self.audio.stop()
        self.memory.close()


def main() -> None:
    assistant = JarvisAssistant()

    def handle_signal(_sig, _frame) -> None:
        assistant.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        assistant.run()
    finally:
        assistant.shutdown()


if __name__ == "__main__":
    main()
