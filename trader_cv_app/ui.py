from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import cv2

from .config import AppConfig, DISCLAIMER
from .data_models import SharedState
from .pipeline import AnalysisPipeline
from .training import train_offline_models


class TradingVisionUI:
    def __init__(self, root: tk.Tk, config: AppConfig):
        self.root = root
        self.config = config
        self.state = SharedState()
        self.pipeline = AnalysisPipeline(config, self.state)
        self.handles = None
        self.training_mode = tk.BooleanVar(value=False)

        self.root.title("Candlestick Vision Predictor (Analysis-Only)")
        self.root.geometry("900x650")

        self.prediction_var = tk.StringVar(value="Prediction: waiting...")
        self.prob_var = tk.StringVar(value="Bullish 50.0% / Bearish 50.0%")
        self.status_var = tk.StringVar(value=DISCLAIMER)

        self._build_layout()
        self._schedule_refresh()

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(top, text="Start", command=self.start).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Stop", command=self.stop).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Train Offline", command=self.train_offline).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(top, text="Training mode (save OHLC CSV)", variable=self.training_mode).pack(side=tk.LEFT, padx=8)

        self.chart_canvas = tk.Canvas(self.root, bg="black", width=860, height=440)
        self.chart_canvas.pack(padx=8, pady=8)

        ttk.Label(self.root, textvariable=self.prediction_var, font=("Arial", 14, "bold")).pack(anchor="w", padx=8)
        ttk.Label(self.root, textvariable=self.prob_var).pack(anchor="w", padx=8)

        self.confidence = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", length=500)
        self.confidence.pack(anchor="w", padx=8, pady=8)

        ttk.Label(self.root, textvariable=self.status_var, foreground="gray").pack(anchor="w", padx=8)

    def start(self) -> None:
        if self.handles is not None:
            return
        try:
            self.state.running = True
            self.handles = self.pipeline.start(record_training_data=self.training_mode.get())
            self.status_var.set("Running. Analysis-only mode enabled.")
        except Exception as exc:
            messagebox.showerror("Failed to start", str(exc))

    def stop(self) -> None:
        if self.handles is None:
            return
        self.pipeline.stop(self.handles)
        self.handles = None
        self.status_var.set("Stopped.")

    def train_offline(self) -> None:
        with self.pipeline._lock:
            feat = self.pipeline._latest_features.copy() if self.pipeline._latest_features is not None else None
        if feat is None or feat.empty:
            messagebox.showwarning("No data", "No extracted candles available yet.")
            return
        ok, msg = train_offline_models(feat, self.config.model_dir, self.config.sequence_length)
        if ok:
            self.pipeline.predictor.load(self.config.model_dir)
            messagebox.showinfo("Training", msg)
        else:
            messagebox.showerror("Training failed", msg)

    def _schedule_refresh(self) -> None:
        self._refresh_chart()
        self._refresh_prediction()
        self.root.after(250, self._schedule_refresh)

    def _refresh_chart(self) -> None:
        self.chart_canvas.delete("all")
        candles = self.state.candles[-50:]
        if not candles:
            return

        width = int(self.chart_canvas["width"])
        height = int(self.chart_canvas["height"])
        step = max(width // max(len(candles), 1), 4)
        x = 10

        for c in candles:
            color = "#2ecc71" if c.bullish else "#e74c3c"
            y_open = int((1 - c.open) * height)
            y_close = int((1 - c.close) * height)
            y_high = int((1 - c.high) * height)
            y_low = int((1 - c.low) * height)
            self.chart_canvas.create_line(x + step // 2, y_high, x + step // 2, y_low, fill=color)
            top = min(y_open, y_close)
            bottom = max(y_open, y_close)
            self.chart_canvas.create_rectangle(x, top, x + step - 2, bottom + 1, fill=color, outline=color)
            x += step

    def _refresh_prediction(self) -> None:
        pred = self.state.latest_prediction
        if pred is None:
            return
        direction = "Bullish" if pred.bullish_probability >= pred.bearish_probability else "Bearish"
        self.prediction_var.set(f"Prediction: {direction}")
        self.prob_var.set(
            f"Bullish {pred.bullish_probability * 100:.1f}% / "
            f"Bearish {pred.bearish_probability * 100:.1f}%"
        )
        self.confidence["value"] = pred.confidence * 100
