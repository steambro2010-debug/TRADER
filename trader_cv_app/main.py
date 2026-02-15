from __future__ import annotations

import tkinter as tk

from .config import AppConfig
from .ui import TradingVisionUI


def main() -> None:
    root = tk.Tk()
    app = TradingVisionUI(root, AppConfig())

    def on_close() -> None:
        app.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
