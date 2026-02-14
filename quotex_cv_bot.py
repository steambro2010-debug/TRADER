import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import yaml
from playwright.sync_api import BrowserContext, Page, sync_playwright


@dataclass
class Candle:
    x: int
    open: float
    high: float
    low: float
    close: float
    is_bullish: bool


@dataclass
class Prediction:
    direction: str
    confidence: float
    eta_seconds: int
    pattern: str
    reason: str


class QuotexWebApp:
    """Launches Quotex in an app-controlled browser so login happens inside the app."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.user_data_dir = cfg["browser"]["user_data_dir"]
        self.url = cfg["browser"]["url"]
        self.viewport = cfg["browser"]["viewport"]
        self.slow_mo = int(cfg["browser"].get("slow_mo_ms", 0))
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        self._playwright = sync_playwright().start()
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            viewport={"width": int(self.viewport["width"]), "height": int(self.viewport["height"])},
            slow_mo=self.slow_mo,
        )
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
        self.page.goto(self.url)

    def capture_frame(self) -> np.ndarray:
        assert self.page is not None
        png_bytes = self.page.screenshot(full_page=False)
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame

    def close(self):
        if self.context:
            self.context.close()
        if hasattr(self, "_playwright"):
            self._playwright.stop()


class CandleExtractor:
    def __init__(self, cfg: dict):
        c = cfg["chart"]
        self.bull_min = np.array(c["bullish_bgr_min"], dtype=np.uint8)
        self.bull_max = np.array(c["bullish_bgr_max"], dtype=np.uint8)
        self.bear_min = np.array(c["bearish_bgr_min"], dtype=np.uint8)
        self.bear_max = np.array(c["bearish_bgr_max"], dtype=np.uint8)
        self.max_candles = int(c["max_candles"])

    def extract(self, roi: np.ndarray) -> List[Candle]:
        bull_mask = cv2.inRange(roi, self.bull_min, self.bull_max)
        bear_mask = cv2.inRange(roi, self.bear_min, self.bear_max)

        kernel = np.ones((3, 3), np.uint8)
        bull_mask = cv2.morphologyEx(bull_mask, cv2.MORPH_OPEN, kernel)
        bear_mask = cv2.morphologyEx(bear_mask, cv2.MORPH_OPEN, kernel)

        candles: List[Candle] = []
        candles.extend(self._from_mask(bull_mask, is_bullish=True))
        candles.extend(self._from_mask(bear_mask, is_bullish=False))
        candles.sort(key=lambda c: c.x)

        merged: List[Candle] = []
        for c in candles:
            if not merged or abs(c.x - merged[-1].x) > 4:
                merged.append(c)
            else:
                if abs(c.low - c.high) > abs(merged[-1].low - merged[-1].high):
                    merged[-1] = c

        return merged[-self.max_candles :]

    def _from_mask(self, mask: np.ndarray, is_bullish: bool) -> List[Candle]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out: List[Candle] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 3 or h < 8:
                continue

            high = float(y)
            low = float(y + h)
            body_top = float(y + h * 0.25)
            body_bottom = float(y + h * 0.75)

            if is_bullish:
                open_, close_ = body_bottom, body_top
            else:
                open_, close_ = body_top, body_bottom

            out.append(Candle(x=x + w // 2, open=open_, high=high, low=low, close=close_, is_bullish=is_bullish))
        return out


class PatternDetector:
    @staticmethod
    def detect(candles: List[Candle]) -> str:
        if len(candles) < 2:
            return "NONE"

        c = candles[-1]
        p = candles[-2]
        body = abs(c.close - c.open)
        wick = abs(c.low - c.high)
        upper = max(0.0, min(c.open, c.close) - c.high)
        lower = max(0.0, c.low - max(c.open, c.close))

        if wick > 0 and body / wick < 0.14:
            return "DOJI"
        if lower > body * 2 and upper < body * 0.6:
            return "HAMMER"

        p_top, p_bottom = min(p.open, p.close), max(p.open, p.close)
        c_top, c_bottom = min(c.open, c.close), max(c.open, c.close)

        if (not p.is_bullish) and c.is_bullish and c_top <= p_top and c_bottom >= p_bottom:
            return "BULLISH_ENGULFING"
        if p.is_bullish and (not c.is_bullish) and c_top <= p_top and c_bottom >= p_bottom:
            return "BEARISH_ENGULFING"

        return "NONE"


class TemplateMatcher:
    """Lightweight template matching to satisfy visual candle matching requirement."""

    def __init__(self):
        self.templates = {
            "SMALL_BODY": self._small_body_template(),
            "LONG_BODY": self._long_body_template(),
        }

    @staticmethod
    def _small_body_template() -> np.ndarray:
        img = np.zeros((20, 8), dtype=np.uint8)
        cv2.line(img, (4, 1), (4, 18), 255, 1)
        cv2.rectangle(img, (2, 8), (6, 12), 255, -1)
        return img

    @staticmethod
    def _long_body_template() -> np.ndarray:
        img = np.zeros((24, 10), dtype=np.uint8)
        cv2.line(img, (5, 1), (5, 22), 255, 1)
        cv2.rectangle(img, (2, 4), (8, 20), 255, -1)
        return img

    def match_score(self, candle_patch: np.ndarray) -> float:
        if candle_patch.size == 0:
            return 0.0
        gray = cv2.cvtColor(candle_patch, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (10, 24))
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        best = 0.0
        for tpl in self.templates.values():
            tpl_resized = cv2.resize(tpl, (bw.shape[1], bw.shape[0]))
            res = cv2.matchTemplate(bw, tpl_resized, cv2.TM_CCOEFF_NORMED)
            best = max(best, float(res.max()))
        return best


class Analyzer:
    @staticmethod
    def support_resistance(candles: List[Candle], lookback: int) -> Tuple[Optional[float], Optional[float]]:
        if not candles:
            return None, None
        sample = candles[-lookback:]
        lows = [c.low for c in sample]
        highs = [c.high for c in sample]
        return float(np.percentile(lows, 20)), float(np.percentile(highs, 80))

    @staticmethod
    def trend_score(candles: List[Candle], lookback: int) -> float:
        if len(candles) < max(5, lookback // 2):
            return 0.0
        closes = np.array([c.close for c in candles[-lookback:]], dtype=np.float32)
        x = np.arange(len(closes), dtype=np.float32)
        slope = np.polyfit(x, closes, 1)[0]
        return float(np.tanh(slope / 2.5))


class Predictor:
    def __init__(self, timeframe_seconds: int):
        self.timeframe_seconds = timeframe_seconds

    def predict(self, candles: List[Candle], trend: float, sr: Tuple[Optional[float], Optional[float]], pattern: str, tpl_score: float) -> Prediction:
        if not candles:
            return Prediction("CALL", 50.0, self.timeframe_seconds, "NONE", "no_data")

        support, resistance = sr
        last = candles[-1]
        bias = trend
        reasons = [f"trend={trend:.2f}", f"tpl={tpl_score:.2f}"]

        if support is not None and resistance is not None:
            if abs(last.close - support) < abs(last.close - resistance):
                bias += 0.12
                reasons.append("near_support")
            else:
                bias -= 0.12
                reasons.append("near_resistance")

        if pattern in ("HAMMER", "BULLISH_ENGULFING"):
            bias += 0.24
        elif pattern == "BEARISH_ENGULFING":
            bias -= 0.24
        elif pattern == "DOJI":
            bias *= 0.5

        if tpl_score > 0.75:
            bias += 0.08 if last.is_bullish else -0.08

        bias = float(np.clip(bias, -1.0, 1.0))
        direction = "CALL" if bias >= 0 else "PUT"
        confidence = round(50 + abs(bias) * 50, 1)
        eta = max(1, self.timeframe_seconds - int(time.time() % self.timeframe_seconds))

        return Prediction(direction, confidence, eta, pattern, ",".join(reasons))


class Logger:
    def __init__(self, enabled: bool, file_path: str):
        self.enabled = enabled
        self.path = Path(file_path)
        if self.enabled and not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["timestamp", "direction", "confidence", "eta", "pattern", "reason"])

    def write(self, p: Prediction):
        if not self.enabled:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.utcnow().isoformat(), p.direction, p.confidence, p.eta_seconds, p.pattern, p.reason])


def select_chart_roi(frame: np.ndarray) -> Tuple[int, int, int, int]:
    print("Select chart area in the screenshot window and press ENTER.")
    roi = cv2.selectROI("Select Quotex Chart", frame, showCrosshair=True)
    cv2.destroyWindow("Select Quotex Chart")
    x, y, w, h = map(int, roi)
    if w <= 0 or h <= 0:
        raise RuntimeError("Invalid ROI selection.")
    return x, y, w, h


def draw_overlay(frame: np.ndarray, pred: Prediction, sr: Tuple[Optional[float], Optional[float]], active: bool):
    support, resistance = sr
    out = frame.copy()
    h, w = out.shape[:2]

    cv2.rectangle(out, (0, 0), (w, 95), (15, 15, 15), -1)
    col = (80, 220, 80) if pred.direction == "CALL" else (80, 80, 220)
    cv2.putText(out, f"Status: {'RUNNING' if active else 'PAUSED'}", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1)
    cv2.putText(out, f"Signal: {pred.direction}   Confidence: {pred.confidence:.1f}%", (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)
    cv2.putText(out, f"Next candle: {pred.eta_seconds}s   Pattern: {pred.pattern}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (220, 220, 220), 1)
    cv2.putText(out, "Hotkeys: S pause/resume | Q quit | L log on/off | +/- alert threshold", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 170, 170), 1)

    if support is not None:
        cv2.line(out, (0, int(support)), (w, int(support)), (0, 200, 200), 1)
    if resistance is not None:
        cv2.line(out, (0, int(resistance)), (w, int(resistance)), (200, 200, 0), 1)

    return out


def beep():
    try:
        import winsound

        winsound.Beep(1150, 150)
    except Exception:
        print("\a", end="")


def load_config(path="config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Missing config.yaml. Copy config.example.yaml to config.yaml first.")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def main():
    cfg = load_config()
    web = QuotexWebApp(cfg)
    extractor = CandleExtractor(cfg)
    matcher = TemplateMatcher()
    predictor = Predictor(cfg["chart"]["timeframe_seconds"])
    logger = Logger(cfg["logging"]["enabled"], cfg["logging"]["file"])

    web.start()
    print("Log in to Quotex in the browser window opened by this app.")
    input("After login and chart setup, press ENTER to continue...")

    first_frame = web.capture_frame()
    roi = select_chart_roi(first_frame)
    x, y, w, h = roi

    active = True
    alert_threshold = int(cfg["prediction"]["min_confidence_alert"])
    last_alert_sec = -1

    while True:
        frame = web.capture_frame()
        chart = frame[y : y + h, x : x + w]

        pred = Prediction("CALL", 50.0, cfg["chart"]["timeframe_seconds"], "NONE", "paused")
        sr = (None, None)

        if active:
            candles = extractor.extract(chart)
            pattern = PatternDetector.detect(candles)
            sr = Analyzer.support_resistance(candles, cfg["prediction"]["support_resistance_lookback"])
            trend = Analyzer.trend_score(candles, cfg["prediction"]["trend_lookback"])

            tpl_score = 0.0
            if candles:
                c = candles[-1]
                cx = int(np.clip(c.x, 8, chart.shape[1] - 8))
                patch = chart[:, max(0, cx - 8) : min(chart.shape[1], cx + 8)]
                tpl_score = matcher.match_score(patch)

            pred = predictor.predict(candles, trend, sr, pattern, tpl_score)
            logger.write(pred)

            now = int(time.time())
            if pred.confidence >= alert_threshold and now != last_alert_sec:
                beep()
                last_alert_sec = now

        overlay = draw_overlay(chart, pred, sr, active)
        cv2.imshow(cfg["ui"]["window_name"], overlay)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("s"):
            active = not active
        if key in (ord("+"), ord("=")):
            alert_threshold = min(100, alert_threshold + 1)
            print(f"alert threshold={alert_threshold}")
        if key in (ord("-"), ord("_")):
            alert_threshold = max(0, alert_threshold - 1)
            print(f"alert threshold={alert_threshold}")
        if key == ord("l"):
            logger.enabled = not logger.enabled
            print(f"logging {'ON' if logger.enabled else 'OFF'}")

    cv2.destroyAllWindows()
    web.close()


if __name__ == "__main__":
    main()
