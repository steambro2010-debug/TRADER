from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, Qt, QPropertyAnimation
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 130))
        self.setGraphicsEffect(shadow)


class AnimatedBar(QProgressBar):
    def __init__(self, color: str) -> None:
        super().__init__()
        self.setRange(0, 100)
        self.setTextVisible(True)
        self.setObjectName("probBar")
        self.setProperty("barColor", color)
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_animated_value(self, val: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(int(max(0, min(100, val))))
        self._anim.start()


class MetricChip(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("metricChip")
        l = QVBoxLayout(self)
        self.k = QLabel(title)
        self.k.setObjectName("chipKey")
        self.v = QLabel("-")
        self.v.setObjectName("chipVal")
        l.addWidget(self.k)
        l.addWidget(self.v)


class AnalyticsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        self.metrics_header = QLabel("CPU -- | FPS -- | Latency -- | Candles 0")
        self.metrics_header.setObjectName("metricsHeader")
        root.addWidget(self.metrics_header)

        self.ai_card = Card()
        ai = QVBoxLayout(self.ai_card)
        self.direction_label = QLabel("UP")
        self.direction_label.setObjectName("directionLabel")
        self.conf_label = QLabel("0.00%")
        self.conf_label.setObjectName("confidenceLabel")
        self.status_label = QLabel("Collecting data: 0 / 10 candles")
        self.model_mode_label = QLabel("Mode: Hybrid")
        ai.addWidget(self.direction_label)
        ai.addWidget(self.conf_label)
        ai.addWidget(self.status_label)
        ai.addWidget(self.model_mode_label)
        root.addWidget(self.ai_card)

        prob_card = Card()
        prob = QVBoxLayout(prob_card)
        self.up_bar = AnimatedBar("#00d17a")
        self.down_bar = AnimatedBar("#ff4d5a")
        self.up_bar.setFormat("UP %p%")
        self.down_bar.setFormat("DOWN %p%")
        prob.addWidget(self.up_bar)
        prob.addWidget(self.down_bar)
        root.addWidget(prob_card)

        self.indicator_toggle = QToolButton()
        self.indicator_toggle.setText("Indicators")
        self.indicator_toggle.setCheckable(True)
        self.indicator_toggle.setChecked(True)
        self.indicator_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.indicator_toggle.setArrowType(Qt.ArrowType.DownArrow)
        self.indicator_toggle.toggled.connect(self._toggle_indicators)
        root.addWidget(self.indicator_toggle)

        self.indicator_panel = Card()
        chips = QHBoxLayout(self.indicator_panel)
        self.rsi_chip = MetricChip("RSI")
        self.macd_chip = MetricChip("MACD Hist")
        self.adx_chip = MetricChip("ADX")
        self.vol_chip = MetricChip("Volatility")
        self.trend_chip = MetricChip("Trend")
        for chip in [self.rsi_chip, self.macd_chip, self.adx_chip, self.vol_chip, self.trend_chip]:
            chips.addWidget(chip)
        root.addWidget(self.indicator_panel)

        controls = Card()
        c_layout = QFormLayout(controls)
        self.auto_toggle = QCheckBox("Auto Trade")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(50, 99)
        self.threshold_slider.setValue(75)
        self.threshold_label = QLabel("Threshold: 75%")
        self.threshold_slider.valueChanged.connect(lambda v: self.threshold_label.setText(f"Threshold: {v}%"))
        self.force_predict_btn = QPushButton("Force Predict")
        c_layout.addRow(self.auto_toggle)
        c_layout.addRow(self.threshold_label, self.threshold_slider)
        c_layout.addRow(self.force_predict_btn)
        root.addWidget(controls)

        table_card = Card()
        t = QVBoxLayout(table_card)
        self.trade_table = QTableWidget(0, 4)
        self.trade_table.setHorizontalHeaderLabels(["Time", "Direction", "Confidence", "Result"])
        t.addWidget(self.trade_table)
        root.addWidget(table_card, 1)

        self.setStyleSheet(
            """
            QWidget { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0b1220, stop:1 #111a2e); color:#d9e6ff; font-family: Inter, Segoe UI, Arial; }
            #card { border:1px solid #223256; border-radius:14px; background-color:#121c33; padding:8px; }
            #directionLabel { font-size:28px; font-weight:800; letter-spacing:1px; }
            #confidenceLabel { font-size:36px; font-weight:900; color:#8ef7bd; }
            #metricsHeader { color:#8ea4d4; font-size:12px; padding:4px 8px; }
            #metricChip { border:1px solid #2a3c65; border-radius:10px; background:#0f1830; padding:6px; }
            #chipKey { color:#8ea4d4; font-size:11px; }
            #chipVal { color:#d9e6ff; font-size:14px; font-weight:700; }
            QProgressBar#probBar { border:1px solid #2a3c65; border-radius:8px; text-align:center; background:#0d162c; height:20px; }
            QProgressBar#probBar::chunk { border-radius:7px; background:#00d17a; }
            QTableWidget { background:#0d162c; border:1px solid #24365f; border-radius:10px; gridline-color:#203056; }
            QPushButton { background:#1b2b4c; border:1px solid #2d467a; border-radius:10px; padding:8px; }
            QPushButton:hover { background:#243a66; }
            """
        )

    def _toggle_indicators(self, expanded: bool) -> None:
        self.indicator_panel.setVisible(expanded)
        self.indicator_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_metrics(self, cpu: float, fps: float, latency_ms: float, candles: int) -> None:
        self.metrics_header.setText(f"CPU {cpu:.0f}% | FPS {fps:.1f} | Latency {latency_ms:.0f}ms | Candles {candles}")

    def update_dashboard(self, direction: str, confidence: float, prob_up: float, prob_down: float, model_mode: str, indicators: dict[str, float]) -> None:
        self.direction_label.setText(direction)
        self.conf_label.setText(f"{confidence:.2f}%")
        self.model_mode_label.setText(f"Mode: {model_mode}")
        self.up_bar.set_animated_value(prob_up)
        self.down_bar.set_animated_value(prob_down)

        self.rsi_chip.v.setText(f"{indicators.get('rsi', 0):.1f}")
        self.macd_chip.v.setText(f"{indicators.get('macd_hist', 0):+.4f}")
        self.adx_chip.v.setText(f"{indicators.get('adx', 0):.1f}")
        self.vol_chip.v.setText(f"{indicators.get('volatility', 0):.4f}")
        self.trend_chip.v.setText(f"{indicators.get('trend_bias', 0):+.2f}")

        threshold = self.threshold_slider.value()
        if confidence >= threshold:
            self.ai_card.setStyleSheet("#card { border:2px solid #00d17a; border-radius:14px; background-color:#12293a; }")
            self.set_status("AI Ready")
        elif confidence < 55:
            self.ai_card.setStyleSheet("#card { border:1px solid #6b2d3d; border-radius:14px; background-color:#2a1520; }")
            self.set_status("Weak Signal")
        else:
            self.ai_card.setStyleSheet("")
            self.set_status("Analyzing…")

    def add_trade(self, direction: str, confidence: float, result: str) -> None:
        row = self.trade_table.rowCount()
        self.trade_table.insertRow(row)
        self.trade_table.setItem(row, 0, QTableWidgetItem("now"))
        self.trade_table.setItem(row, 1, QTableWidgetItem(direction))
        self.trade_table.setItem(row, 2, QTableWidgetItem(f"{confidence:.2f}%"))
        self.trade_table.setItem(row, 3, QTableWidgetItem(result))

        color = QColor("#1f4d2f") if "win" in result.lower() else QColor("#4d1f2b") if "loss" in result.lower() else QColor("#1b2b4c")
        for col in range(4):
            item = self.trade_table.item(row, col)
            if item:
                item.setBackground(color)


class MainWindow(QMainWindow):
    def __init__(self, browser_widget: QWidget) -> None:
        super().__init__()
        self.setWindowTitle("Quotex AI Trading Intelligence")
        self.resize(1680, 940)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        browser_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(browser_widget)

        self.panel = AnalyticsPanel()

        central = QWidget()
        central.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(central)
        layout.addWidget(browser_widget, 4)
        layout.addWidget(self.panel, 2)
        self.setCentralWidget(central)
