import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int


class RegionSelector:
    def __init__(self, logger) -> None:
        self.logger = logger

    def select(self) -> Optional[Region]:
        try:
            import tkinter as tk
        except Exception as exc:
            self.logger.error("Tkinter unavailable for region selection: %s", exc)
            return None

        selection = {"start": None, "end": None}
        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.attributes("-alpha", 0.25)
        root.configure(bg="black")
        root.title("Select Quotex chart region")

        canvas = tk.Canvas(root, cursor="cross", bg="#111111", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        rect_id = None

        def on_press(event):
            nonlocal rect_id
            selection["start"] = (event.x, event.y)
            rect_id = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#00ccff", width=3)

        def on_drag(event):
            if selection["start"] and rect_id:
                canvas.coords(rect_id, selection["start"][0], selection["start"][1], event.x, event.y)

        def on_release(event):
            selection["end"] = (event.x, event.y)
            root.quit()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.mainloop()
        root.destroy()

        if not selection["start"] or not selection["end"]:
            return None

        x1, y1 = selection["start"]
        x2, y2 = selection["end"]
        left, top = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)
        if width < 40 or height < 40:
            self.logger.warning("Region too small; please rerun and select a larger chart area.")
            return None
        return Region(left=left, top=top, width=width, height=height)


class ScreenCaptureEngine:
    def __init__(self, region: Region, fps_cap: int, frame_queue: queue.Queue, metrics: dict, logger) -> None:
        self.region = region
        self.fps_cap = fps_cap
        self.frame_queue = frame_queue
        self.metrics = metrics
        self.logger = logger
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="capture-thread", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            import mss
        except Exception as exc:
            self.logger.error("mss is required for screen capture: %s", exc)
            return

        self.logger.info("Screen capture started at %s FPS", self.fps_cap)
        frame_interval = 1.0 / max(self.fps_cap, 1)
        with mss.mss() as sct:
            monitor = {
                "left": self.region.left,
                "top": self.region.top,
                "width": self.region.width,
                "height": self.region.height,
            }
            last_frame_at = time.perf_counter()
            frame_counter = 0
            fps_start = time.perf_counter()
            while not self.stop_event.is_set():
                grabbed = sct.grab(monitor)
                frame = np.array(grabbed)
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                timestamp = time.time()
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.frame_queue.put((timestamp, bgr_frame))
                frame_counter += 1

                elapsed = time.perf_counter() - fps_start
                if elapsed >= 1.0:
                    self.metrics["fps"] = round(frame_counter / elapsed, 1)
                    fps_start = time.perf_counter()
                    frame_counter = 0

                spent = time.perf_counter() - last_frame_at
                wait = frame_interval - spent
                if wait > 0:
                    time.sleep(wait)
                last_frame_at = time.perf_counter()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
