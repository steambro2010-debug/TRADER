import csv
import math
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import cv2
import mss
import numpy as np
import yaml


@dataclass
class Candle:
    timestamp: float
    x: int
    open: float
    high: float
    low: float
    close: float
    body_top: int
    body_bottom: int
    wick_top: int
    wick_bottom: int
    is_bullish: bool


@dataclass
class Prediction:
    direction: str  # CALL / PUT
    confidence: float
    eta_seconds: int
    pattern: str
    reason: str


class ScreenCapture:
    def __init__(self, monitor: int, region: dict):
        self.sct = mss.mss()
        self.monitor = monitor
        self.region = {
            "left": int(region["left"]),
            "top": int(region["top"]),
            "width": int(region["width"]),
            "height": int(region["height"]),
            "mon": monitor,
        }

    def grab(self) -> np.ndarray:
        img = self.sct.grab(self.region)
        frame = np.array(img)[:, :, :3]
        return frame


class CandleExtractor:
    def __init__(self, cfg: dict):
        c = cfg["chart"]
        self.bull_min = np.array(c["bullish_bgr_min"], dtype=np.uint8)
        self.bull_max = np.array(c["bullish_bgr_max"], dtype=np.uint8)
        self.bear_min = np.array(c["bearish_bgr_min"], dtype=np.uint8)
        self.bear_max = np.array(c["bearish_bgr_max"], dtype=np.uint8)
        self.max_candles = int(c["max_candles"])

    @staticmethod
    def _mask_cleanup(mask: np.ndarray) -> np.ndarray:
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return mask

    def _contours_to_candles(self, mask: np.ndarray, is_bullish: bool, ts: float) -> List[Candle]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 3 or h < 6:
                continue
            wick_top = y
            wick_bottom = y + h

            body_top = y + int(h * 0.25)
            body_bottom = y + int(h * 0.75)
            if is_bullish:
                open_px = body_bottom
                close_px = body_top
            else:
                open_px = body_top
                close_px = body_bottom

            out.append(
                Candle(
                    timestamp=ts,
                    x=x + w // 2,
                    open=float(open_px),
                    high=float(wick_top),
                    low=float(wick_bottom),
                    close=float(close_px),
                    body_top=body_top,
                    body_bottom=body_bottom,
                    wick_top=wick_top,
                    wick_bottom=wick_bottom,
                    is_bullish=is_bullish,
                )
            )

        out.sort(key=lambda c: c.x)
        return out

    def extract(self, frame: np.ndarray, ts: float) -> List[Candle]:
        bull_mask = cv2.inRange(frame, self.bull_min, self.bull_max)
        bear_mask = cv2.inRange(frame, self.bear_min, self.bear_max)

        bull_mask = self._mask_cleanup(bull_mask)
        bear_mask = self._mask_cleanup(bear_mask)

        candles = self._contours_to_candles(bull_mask, True, ts) + self._contours_to_candles(bear_mask, False, ts)
        candles.sort(key=lambda c: c.x)

        merged = []
        for c in candles:
            if not merged or abs(c.x - merged[-1].x) > 4:
                merged.append(c)
            else:
                prev = merged[-1]
                if c.wick_bottom - c.wick_top > prev.wick_bottom - prev.wick_top:
                    merged[-1] = c

        return merged[-self.max_candles :]


class PatternDetector:
    @staticmethod
    def detect(candles: List[Candle]) -> str:
        if len(candles) < 2:
            return "NONE"

        c = candles[-1]
        prev = candles[-2]
        body = abs(c.close - c.open)
        wick_total = abs(c.low - c.high)
        upper_wick = max(0.0, min(c.open, c.close) - c.high)
        lower_wick = max(0.0, c.low - max(c.open, c.close))

        if wick_total > 0 and body / wick_total < 0.15:
            return "DOJI"
        if lower_wick > body * 2 and upper_wick < body * 0.5:
            return "HAMMER"

        prev_body_top = min(prev.open, prev.close)
        prev_body_bottom = max(prev.open, prev.close)
        c_body_top = min(c.open, c.close)
        c_body_bottom = max(c.open, c.close)

        bullish_engulf = (not prev.is_bullish and c.is_bullish and c_body_top <= prev_body_top and c_body_bottom >= prev_body_bottom)
        bearish_engulf = (prev.is_bullish and not c.is_bullish and c_body_top <= prev_body_top and c_body_bottom >= prev_body_bottom)
        if bullish_engulf:
            return "BULLISH_ENGULFING"
        if bearish_engulf:
            return "BEARISH_ENGULFING"

        return "NONE"


class TechnicalAnalyzer:
    @staticmethod
    def support_resistance(candles: List[Candle], lookback: int = 80) -> Tuple[Optional[float], Optional[float]]:
        if not candles:
            return None, None
        sample = candles[-lookback:]
        lows = sorted([c.low for c in sample])
        highs = sorted([c.high for c in sample])
        support = float(np.percentile(lows, 20)) if lows else None
        resistance = float(np.percentile(highs, 80)) if highs else None
        return support, resistance

    @staticmethod
    def trend_score(candles: List[Candle], lookback: int = 20) -> float:
        if len(candles) < max(5, lookback // 2):
            return 0.0
        sample = candles[-lookback:]
        closes = np.array([c.close for c in sample], dtype=np.float32)
        x = np.arange(len(closes), dtype=np.float32)
        slope = np.polyfit(x, closes, 1)[0]
        normalized = float(np.tanh(slope / 3.0))
        return normalized


class PredictionEngine:
    def __init__(self, timeframe_seconds: int):
        self.timeframe_seconds = timeframe_seconds

    def predict(self, candles: List[Candle], trend_score: float, support: Optional[float], resistance: Optional[float], pattern: str) -> Prediction:
        if not candles:
            return Prediction("CALL", 50.0, self.timeframe_seconds, "NONE", "No candle data")

        last = candles[-1]
        bias = trend_score
        reason_parts = [f"trend={trend_score:.2f}"]

        if support is not None and resistance is not None:
            dist_to_support = abs(last.close - support)
            dist_to_resistance = abs(last.close - resistance)
            if dist_to_support < dist_to_resistance:
                bias += 0.15
                reason_parts.append("near_support")
            else:
                bias -= 0.15
                reason_parts.append("near_resistance")

        if pattern == "BULLISH_ENGULFING" or pattern == "HAMMER":
            bias += 0.25
        elif pattern == "BEARISH_ENGULFING":
            bias -= 0.25
        elif pattern == "DOJI":
            bias *= 0.4
        if pattern != "NONE":
            reason_parts.append(pattern)

        bias = float(np.clip(bias, -1.0, 1.0))
        direction = "CALL" if bias >= 0 else "PUT"
        confidence = 50.0 + abs(bias) * 50.0

        now = time.time()
        elapsed = int(now % self.timeframe_seconds)
        eta = max(1, self.timeframe_seconds - elapsed)

        return Prediction(direction, round(confidence, 1), eta, pattern, ",".join(reason_parts))


class BotUI:
    def __init__(self, cfg: dict):
        self.window_name = cfg["ui"]["window_name"]
        self.font_scale = float(cfg["ui"]["font_scale"])

    def draw_overlay(
        self,
        frame: np.ndarray,
        prediction: Prediction,
        candles: List[Candle],
        support: Optional[float],
        resistance: Optional[float],
        active: bool,
    ) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        panel_h = 110
        cv2.rectangle(out, (0, 0), (w, panel_h), (15, 15, 15), -1)

        status = "RUNNING" if active else "PAUSED"
        color = (80, 220, 80) if prediction.direction == "CALL" else (80, 80, 220)
        cv2.putText(out, f"Status: {status}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (240, 240, 240), 1)
        cv2.putText(out, f"Signal: {prediction.direction}  Confidence: {prediction.confidence:.1f}%", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, color, 2)
        cv2.putText(out, f"Next candle in: {prediction.eta_seconds}s  Pattern: {prediction.pattern}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (220, 220, 220), 1)
        cv2.putText(out, "Hotkeys: S=start/stop  +/- alert threshold  L=log toggle  Q=quit", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (170, 170, 170), 1)

        if candles:
            last = candles[-1]
            arrow_start = (w - 180, int(last.close))
            arrow_end = (w - 100, int(last.close - 30 if prediction.direction == "CALL" else last.close + 30))
            cv2.arrowedLine(out, arrow_start, arrow_end, color, 2, tipLength=0.2)

        if support is not None:
            y = int(support)
            cv2.line(out, (0, y), (w, y), (0, 200, 200), 1)
        if resistance is not None:
            y = int(resistance)
            cv2.line(out, (0, y), (w, y), (200, 200, 0), 1)

        return out


def beep():
    try:
        import winsound

        winsound.Beep(1200, 160)
    except Exception:
        print("\a", end="")


class PredictionLogger:
    def __init__(self, enabled: bool, path: str):
        self.enabled = enabled
        self.path = Path(path)
        if self.enabled and not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "direction", "confidence", "eta_seconds", "pattern", "reason"])

    def log(self, p: Prediction):
        if not self.enabled:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([datetime.utcnow().isoformat(), p.direction, p.confidence, p.eta_seconds, p.pattern, p.reason])


def load_config(path: str = "config.yaml") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError("config.yaml not found. Copy config.example.yaml to config.yaml and edit region/colors first.")
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    capture = ScreenCapture(cfg["screen"]["monitor"], cfg["screen"]["region"])
    extractor = CandleExtractor(cfg)
    predictor = PredictionEngine(cfg["chart"]["timeframe_seconds"])
    ui = BotUI(cfg)

    logging_cfg = cfg["logging"]
    logger = PredictionLogger(logging_cfg["enabled"], logging_cfg["file"])

    active = True
    frame_counter = 0
    alert_threshold = int(cfg["prediction"]["min_confidence_alert"])
    last_alert_second = -1
    pattern = "NONE"

    print("Starting Quotex CV Bot. Press Q in window to quit.")

    while True:
        frame = capture.grab()
        ts = time.time()
        frame_counter += 1

        candles = []
        support = resistance = None
        pred = Prediction("CALL", 50.0, cfg["chart"]["timeframe_seconds"], "NONE", "paused")

        if active and frame_counter % int(cfg["prediction"]["process_every_n_frames"]) == 0:
            candles = extractor.extract(frame, ts)
            pattern = PatternDetector.detect(candles)
            support, resistance = TechnicalAnalyzer.support_resistance(candles, cfg["prediction"]["support_resistance_lookback"])
            trend = TechnicalAnalyzer.trend_score(candles, cfg["prediction"]["trend_lookback"])
            pred = predictor.predict(candles, trend, support, resistance, pattern)
            logger.log(pred)

            now_sec = int(time.time())
            if pred.confidence >= alert_threshold and now_sec != last_alert_second:
                beep()
                last_alert_second = now_sec

        if cfg["ui"]["show_overlay"]:
            shown = ui.draw_overlay(frame, pred, candles, support, resistance, active)
        else:
            shown = frame

        cv2.imshow(cfg["ui"]["window_name"], shown)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key in (ord("s"),):
            active = not active
        if key in (ord("+"), ord("=")):
            alert_threshold = min(100, alert_threshold + 1)
            print(f"Alert threshold: {alert_threshold}%")
        if key in (ord("-"), ord("_")):
            alert_threshold = max(0, alert_threshold - 1)
            print(f"Alert threshold: {alert_threshold}%")
        if key in (ord("l"),):
            logger.enabled = not logger.enabled
            print(f"Logging {'enabled' if logger.enabled else 'disabled'}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
