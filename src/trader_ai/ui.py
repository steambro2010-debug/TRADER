from __future__ import annotations

import tkinter as tk

from .pipeline import RealtimePipeline


class TradingSignalUI:
    def __init__(self, pipeline: RealtimePipeline):
        self.pipeline = pipeline
        self.root = tk.Tk()
        self.root.title("Live Screen AI Trading Signals")
        self.root.geometry("540x320")

        self.lbl_candle = tk.Label(self.root, text="Candle: N/A", font=("Arial", 11), anchor="w", justify="left")
        self.lbl_candle.pack(fill="x", padx=10, pady=8)

        self.lbl_signal = tk.Label(self.root, text="Signal: N/A", font=("Arial", 14, "bold"), anchor="w")
        self.lbl_signal.pack(fill="x", padx=10, pady=8)

        self.lbl_accuracy = tk.Label(self.root, text="Rolling Accuracy: 0.00%", font=("Arial", 11), anchor="w")
        self.lbl_accuracy.pack(fill="x", padx=10, pady=8)

        self.btn_toggle = tk.Button(self.root, text="Toggle Prediction", command=self._toggle)
        self.btn_toggle.pack(padx=10, pady=10)

        self.status = tk.Label(self.root, text="Prediction ON", fg="green")
        self.status.pack(padx=10, pady=4)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle(self) -> None:
        self.pipeline.toggle_predictions()
        enabled = self.pipeline.state.prediction_enabled
        self.status.config(text=f"Prediction {'ON' if enabled else 'OFF'}", fg="green" if enabled else "red")

    def _on_close(self) -> None:
        self.pipeline.stop()
        self.root.destroy()

    def _refresh(self) -> None:
        st = self.pipeline.state
        if st.last_candle is not None:
            c = st.last_candle
            self.lbl_candle.config(
                text=(
                    f"Candle @ {c.timestamp:.0f}\n"
                    f"O: {c.open:.5f}  H: {c.high:.5f}\n"
                    f"L: {c.low:.5f}  C: {c.close:.5f}"
                )
            )
        self.lbl_signal.config(text=f"Signal: {st.last_signal} ({st.last_confidence:.2%})")
        self.lbl_accuracy.config(text=f"Rolling Accuracy: {st.rolling_accuracy:.2%}")
        self.root.after(250, self._refresh)

    def run(self) -> None:
        self.pipeline.start()
        self._refresh()
        self.root.mainloop()
