from __future__ import annotations

import threading


class OverlayGUI:
    def __init__(self) -> None:
        self._latest: dict = {}
        self._enabled = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            from PySide6.QtCore import Qt, QTimer
            from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
        except Exception:
            return

        self._enabled = True

        def run():
            app = QApplication([])
            panel = QWidget()
            panel.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            panel.setAttribute(Qt.WA_TranslucentBackground)
            panel.setStyleSheet(
                """
                QWidget { background-color: rgba(16,16,20,180); border-radius: 10px; color: #e8e8e8; }
                QPushButton { background-color: #2f80ed; color: white; border-radius: 6px; padding: 6px; }
                """
            )
            layout = QVBoxLayout(panel)
            label = QLabel("Waiting for data...")
            auto_btn = QPushButton("Auto Trade OFF")
            layout.addWidget(label)
            layout.addWidget(auto_btn)

            timer = QTimer()

            def refresh():
                if self._latest:
                    label.setText("\n".join([f"{k}: {v}" for k, v in self._latest.items()]))

            timer.timeout.connect(refresh)
            timer.start(250)
            panel.resize(360, 180)
            panel.show()
            app.exec()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def update(self, signal, ml_prediction) -> None:
        payload = {
            "Direction": signal.direction,
            "Confidence": f"{signal.confidence:.2f}%",
            "ML_UP": f"{ml_prediction.prob_up:.2f}%",
            "ML_DOWN": f"{ml_prediction.prob_down:.2f}%",
            "Reason": signal.reason,
        }
        self._latest = payload
