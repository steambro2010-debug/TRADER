from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from strategy.signal_generator import Signal


class AnalyticsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        layout = QVBoxLayout(self)

        self.direction_label = QLabel("Direction: -")
        self.model_label = QLabel("Model prob: -")
        self.status_label = QLabel("Status: Waiting for data")
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setFormat("Confidence %p%")
        self.conf_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.auto_toggle = QCheckBox("Auto Trade")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(50, 99)
        self.threshold_slider.setValue(75)
        self.threshold_label = QLabel("Threshold: 75%")
        self.threshold_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.threshold_slider.valueChanged.connect(lambda v: self.threshold_label.setText(f"Threshold: {v}%"))

        self.heatmap_label = QLabel("Indicator heatmap: RSI -, ADX -")
        self.heatmap_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.trade_table = QTableWidget(0, 4)
        self.trade_table.setHorizontalHeaderLabels(["Time", "Dir", "Conf", "Result"])

        form = QFormLayout()
        form.addRow(self.auto_toggle)
        form.addRow(self.threshold_label, self.threshold_slider)

        layout.addWidget(self.direction_label)
        layout.addWidget(self.model_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.conf_bar)
        layout.addLayout(form)
        layout.addWidget(self.heatmap_label)
        layout.addWidget(self.trade_table)

    def set_status(self, text: str) -> None:
        self.status_label.setText(f"Status: {text}")

    def update_signal(self, signal: Signal) -> None:
        self.direction_label.setText(f"Direction: {signal.direction}")
        self.model_label.setText(f"Model prob: {signal.model_probability:.2f}%")
        self.conf_bar.setValue(int(signal.confidence))
        self.heatmap_label.setText(
            f"Indicator heatmap: RSI {signal.diagnostics.get('rsi', 0):.1f}, ADX {signal.diagnostics.get('adx', 0):.1f}"
        )
        self.set_status("Prediction active")

    def add_trade(self, direction: str, confidence: float, result: str) -> None:
        row = self.trade_table.rowCount()
        self.trade_table.insertRow(row)
        self.trade_table.setItem(row, 0, QTableWidgetItem("now"))
        self.trade_table.setItem(row, 1, QTableWidgetItem(direction))
        self.trade_table.setItem(row, 2, QTableWidgetItem(f"{confidence:.2f}%"))
        self.trade_table.setItem(row, 3, QTableWidgetItem(result))


class MainWindow(QMainWindow):
    def __init__(self, browser_widget: QWidget) -> None:
        super().__init__()
        self.setWindowTitle("Quotex WebSocket Trading Engine")
        self.resize(1560, 900)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        browser_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(browser_widget)

        self.panel = AnalyticsPanel()

        central = QWidget()
        central.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(central)
        layout.addWidget(browser_widget, 3)
        layout.addWidget(self.panel, 1)
        self.setCentralWidget(central)
