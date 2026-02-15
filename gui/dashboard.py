import tkinter as tk
from tkinter import ttk
from typing import Dict, List


class Dashboard:
    def __init__(self, state: Dict, stop_callback, logger) -> None:
        self.state = state
        self.stop_callback = stop_callback
        self.logger = logger
        self.root = tk.Tk()
        self.root.title("Quotex Trading Assistant")
        self.root.geometry("1080x700")
        self.root.configure(bg="#0f141a")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background="#161d26")
        style.configure("Dark.TLabel", background="#161d26", foreground="#e6edf3")

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, style="Dark.TFrame", padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="CPU: -- | FPS: -- | Buffer: 0 | AI: idle")
        status_bar = ttk.Label(container, textvariable=self.status_var, style="Dark.TLabel", font=("Segoe UI", 11, "bold"))
        status_bar.pack(fill=tk.X, pady=(0, 10))

        main_card = tk.Frame(container, bg="#1b2633", bd=0, padx=20, pady=16)
        main_card.pack(fill=tk.X)

        self.direction_var = tk.StringVar(value="WAITING")
        self.confidence_var = tk.StringVar(value="0.00%")
        self.mode_var = tk.StringVar(value="Mode: initializing")

        tk.Label(main_card, textvariable=self.direction_var, font=("Segoe UI", 38, "bold"), fg="#4dd2ff", bg="#1b2633").pack(anchor="w")
        tk.Label(main_card, textvariable=self.confidence_var, font=("Segoe UI", 30, "bold"), fg="#7ee787", bg="#1b2633").pack(anchor="w")
        tk.Label(main_card, textvariable=self.mode_var, font=("Segoe UI", 12), fg="#9da7b3", bg="#1b2633").pack(anchor="w")

        probs = tk.Frame(container, bg="#0f141a")
        probs.pack(fill=tk.X, pady=12)
        self.up_bar = ttk.Progressbar(probs, maximum=100)
        self.down_bar = ttk.Progressbar(probs, maximum=100)
        tk.Label(probs, text="UP", fg="#e6edf3", bg="#0f141a", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.up_bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(probs, text="DOWN", fg="#e6edf3", bg="#0f141a", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.down_bar.pack(fill=tk.X)

        self.ind_var = tk.StringVar(value="RSI -- | MACD -- | ADX -- | Volatility -- | Trend --")
        ind_card = tk.Frame(container, bg="#161d26", padx=12, pady=10)
        ind_card.pack(fill=tk.X, pady=12)
        tk.Label(ind_card, textvariable=self.ind_var, fg="#e6edf3", bg="#161d26", font=("Consolas", 11)).pack(anchor="w")

        log_card = tk.Frame(container, bg="#161d26", padx=10, pady=10)
        log_card.pack(fill=tk.BOTH, expand=True)
        tk.Label(log_card, text="Trade Log", fg="#e6edf3", bg="#161d26", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.log = tk.Text(log_card, bg="#0f141a", fg="#c9d1d9", height=10, relief=tk.FLAT, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    def _on_close(self) -> None:
        self.stop_callback()
        self.root.destroy()

    def add_trade_log(self, rows: List[str]) -> None:
        self.log.delete("1.0", tk.END)
        for row in rows[-30:]:
            self.log.insert(tk.END, row + "\n")

    def refresh(self) -> None:
        metrics = self.state.get("metrics", {})
        pred = self.state.get("prediction")
        self.status_var.set(
            f"CPU: {metrics.get('cpu', '--')}% | FPS: {metrics.get('fps', '--')} | "
            f"Buffer: {metrics.get('buffer_size', 0)} | AI: {self.state.get('ai_status', 'idle')}"
        )

        if pred:
            self.direction_var.set(pred.direction)
            self.confidence_var.set(f"{pred.confidence * 100:.2f}%")
            self.mode_var.set(f"Mode: {pred.mode}")
            self.up_bar["value"] = pred.up_probability * 100
            self.down_bar["value"] = pred.down_probability * 100
            self.ind_var.set(
                "RSI {rsi} | MACD {macd} | ADX {adx} | Volatility {volatility} | Trend {trend}".format(**pred.indicators)
            )

        self.add_trade_log(self.state.get("trade_log", []))
        self.root.after(400, self.refresh)

    def run(self) -> None:
        self.refresh()
        self.root.mainloop()
