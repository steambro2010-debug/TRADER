from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, SAFETY_TEXT
from .data_models import ModelStatus, PipelineStatus, SharedState
from .pipeline import PipelineController

logger = logging.getLogger(__name__)


class CandleChartWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.candles = []
        self.setMinimumHeight(340)
        self.setStyleSheet("background-color: #111318; border: 1px solid #2A2E39;")

    def set_candles(self, candles):
        self.candles = candles[-100:]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.candles:
            painter.setPen(QColor("#999"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Loading candles...")
            return

        w = self.width()
        h = self.height()
        step = max(5, w // max(len(self.candles), 1))
        x = 8

        for c in self.candles:
            color = QColor("#21c55d") if c.bullish else QColor("#ef4444")
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)

            y_open = int((1.0 - c.open) * (h - 10))
            y_close = int((1.0 - c.close) * (h - 10))
            y_high = int((1.0 - c.high) * (h - 10))
            y_low = int((1.0 - c.low) * (h - 10))

            painter.drawLine(x + step // 2, y_high, x + step // 2, y_low)
            top = min(y_open, y_close)
            body_h = max(2, abs(y_close - y_open))
            painter.fillRect(x, top, max(2, step - 2), body_h, color)
            x += step


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.state = SharedState()
        self.controller = PipelineController(config, self.state)

        self.setWindowTitle("Candlestick Vision Predictor")
        self.resize(1080, 720)
        self._build_ui()
        self._apply_dark_theme()

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_ui)
        self.ui_timer.start(120)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.train_btn = QPushButton("Train Offline")
        self.train_toggle = QCheckBox("Training mode (append CSV)")

        self.start_btn.clicked.connect(self.start_pipeline)
        self.stop_btn.clicked.connect(self.stop_pipeline)
        self.train_btn.clicked.connect(self.train_models)

        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.train_btn)
        top.addWidget(self.train_toggle)
        top.addStretch(1)

        root.addLayout(top)

        self.chart = CandleChartWidget()
        root.addWidget(self.chart)

        self.prediction_label = QLabel("Prediction: model not ready")
        self.probability_label = QLabel("Bullish: -- % | Bearish: -- %")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)

        self.fps_label = QLabel("FPS: 0.0")
        self.model_status_label = QLabel("Model: UNTRAINED")
        self.pipeline_status_label = QLabel("Status: LOADING")
        self.safety_label = QLabel(SAFETY_TEXT)

        for widget in [
            self.prediction_label,
            self.probability_label,
            self.fps_label,
            self.model_status_label,
            self.pipeline_status_label,
            self.safety_label,
        ]:
            root.addWidget(widget)

        root.addWidget(self.confidence_bar)
        self.setCentralWidget(central)

    def _apply_dark_theme(self):
        self.setStyleSheet(
            """
            QWidget { background-color: #0b0f14; color: #e6edf3; font-size: 13px; }
            QPushButton { background-color: #1f2937; border: 1px solid #374151; padding: 6px 10px; }
            QPushButton:hover { background-color: #374151; }
            QProgressBar { border: 1px solid #374151; text-align: center; }
            QProgressBar::chunk { background-color: #3b82f6; }
            """
        )

    def start_pipeline(self):
        try:
            self.controller.start(record_training_data=self.train_toggle.isChecked())
        except Exception as exc:
            QMessageBox.critical(self, "Start failed", str(exc))

    def stop_pipeline(self):
        self.controller.stop()

    def train_models(self):
        ok, msg = self.controller.train_offline()
        box = QMessageBox.information if ok else QMessageBox.warning
        box(self, "Training", msg)

    def refresh_ui(self):
        self.chart.set_candles(self.state.candles)
        self.fps_label.setText(f"FPS: {self.state.capture_fps:.1f}")

        self.model_status_label.setText(f"Model: {self.state.model_status.value} | {self.state.model_message}")
        self.pipeline_status_label.setText(f"Status: {self.state.pipeline_status.value} | {self.state.pipeline_message}")

        if self.state.pipeline_status == PipelineStatus.ERROR:
            self.pipeline_status_label.setStyleSheet("color:#ef4444")
        elif self.state.pipeline_status == PipelineStatus.WARNING:
            self.pipeline_status_label.setStyleSheet("color:#f59e0b")
        else:
            self.pipeline_status_label.setStyleSheet("color:#22c55e")

        if self.state.model_status != ModelStatus.READY or self.state.prediction is None:
            self.prediction_label.setText("Prediction: unavailable")
            self.probability_label.setText("Bullish: -- % | Bearish: -- %")
            self.confidence_bar.setValue(0)
            return

        pred = self.state.prediction
        direction = "Bullish" if pred.bullish_probability >= pred.bearish_probability else "Bearish"
        self.prediction_label.setText(f"Prediction: {direction}")
        self.probability_label.setText(
            f"Bullish: {pred.bullish_probability * 100:.2f}% | "
            f"Bearish: {pred.bearish_probability * 100:.2f}%"
        )
        self.confidence_bar.setValue(int(pred.confidence * 100))


def run_app(config: AppConfig):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(config)
    window.show()
    app.exec()
