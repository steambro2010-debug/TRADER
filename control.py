from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import psutil
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True


@dataclass(slots=True)
class ActionResult:
    success: bool
    detail: str


class DesktopController:
    def open_app(self, command: str) -> ActionResult:
        try:
            subprocess.Popen(command, shell=True)
            return ActionResult(True, f"Opened: {command}")
        except Exception as exc:
            return ActionResult(False, f"Failed opening {command}: {exc}")

    def close_app(self, process_name: str) -> ActionResult:
        killed = 0
        for proc in psutil.process_iter(["name"]):
            if proc.info.get("name", "").lower().startswith(process_name.lower()):
                proc.kill()
                killed += 1
        return ActionResult(killed > 0, f"Killed {killed} process(es) named {process_name}")

    def switch_window(self, title_keyword: str) -> ActionResult:
        wins = gw.getWindowsWithTitle(title_keyword)
        if not wins:
            return ActionResult(False, f"No window containing '{title_keyword}'")
        wins[0].activate()
        return ActionResult(True, f"Switched to {wins[0].title}")

    def type_text(self, text: str, interval: float = 0.015) -> ActionResult:
        pyautogui.write(text, interval=interval)
        return ActionResult(True, "Text entered")

    def hotkey(self, *keys: str) -> ActionResult:
        pyautogui.hotkey(*keys)
        return ActionResult(True, f"Pressed {'+'.join(keys)}")

    def click(self, x: int, y: int, button: str = "left") -> ActionResult:
        pyautogui.click(x=x, y=y, button=button)
        return ActionResult(True, f"Clicked {button} at ({x},{y})")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.4) -> ActionResult:
        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=duration)
        return ActionResult(True, f"Dragged from ({x1},{y1}) to ({x2},{y2})")

    def scroll(self, amount: int) -> ActionResult:
        pyautogui.scroll(amount)
        return ActionResult(True, f"Scrolled {amount}")

    def open_file(self, path: str) -> ActionResult:
        target = Path(path).expanduser()
        if not target.exists():
            return ActionResult(False, f"File not found: {target}")
        os.startfile(str(target))
        return ActionResult(True, f"Opened file {target}")

    def search_files(self, root: str, query: str, limit: int = 20) -> list[str]:
        root_path = Path(root).expanduser()
        matches: list[str] = []
        for base, _, files in os.walk(root_path):
            for name in files:
                if query.lower() in name.lower():
                    matches.append(str(Path(base) / name))
                    if len(matches) >= limit:
                        return matches
        return matches

    def search_text_in_files(self, root: str, text: str, extensions: Optional[Iterable[str]] = None) -> list[str]:
        root_path = Path(root).expanduser()
        allowed = {ext.lower() for ext in extensions} if extensions else None
        hits: list[str] = []

        for base, _, files in os.walk(root_path):
            for name in files:
                ext = Path(name).suffix.lower()
                if allowed and ext not in allowed:
                    continue
                file_path = Path(base) / name
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if text.lower() in content.lower():
                    hits.append(str(file_path))
        return hits

    def close_unnecessary_apps(self, protected: Optional[set[str]] = None) -> ActionResult:
        protected = {"explorer.exe", "dwm.exe", "winlogon.exe", "System", *(protected or set())}
        closed = 0
        for proc in psutil.process_iter(["name", "cpu_percent"]):
            name = proc.info.get("name") or ""
            if name in protected:
                continue
            cpu = proc.info.get("cpu_percent") or 0
            if cpu < 1.0:
                continue
            try:
                proc.terminate()
                closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            time.sleep(0.02)
        return ActionResult(True, f"Requested shutdown for {closed} busy apps")
