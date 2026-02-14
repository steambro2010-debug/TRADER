import csv
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np
import yaml
from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


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
    score: float


@dataclass
class PendingPrediction:
    candle_index: int
    score: float
    features: np.ndarray


class QuotexWebApp:
    def __init__(self, cfg: dict):
        bcfg = cfg["browser"]
        self.user_data_dir = bcfg["user_data_dir"]
        self.url = bcfg["url"]
        self.viewport = bcfg["viewport"]
        self.slow_mo = int(bcfg.get("slow_mo_ms", 0))
        self.channel = bcfg.get("channel", "chrome")
        self.security_timeout = int(bcfg.get("security_wait_timeout_seconds", 300))
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        self._playwright = sync_playwright().start()
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            channel=self.channel,
            viewport={"width": int(self.viewport["width"]), "height": int(self.viewport["height"])},
            slow_mo=self.slow_mo,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.goto(self.url, wait_until="domcontentloaded")

    def wait_for_manual_security_clear(self):
        assert self.page is not None
        print("If security verification appears, solve it in the browser window first.")
        deadline = time.time() + self.security_timeout
        markers = ["performing security verification", "verifies you are not a bot", "security service"]

        while time.time() < deadline:
            try:
                self.page.wait_for_timeout(1000)
                text = self.page.inner_text("body").lower()[:5000]
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

            if any(m in text for m in markers):
                continue
            return

        print("Verification timeout reached; continue manually once chart is visible.")

    def capture_frame(self) -> np.ndarray:
        assert self.page is not None
        png_bytes = self.page.screenshot(full_page=False)
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

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

        candles = self._from_mask(bull_mask, True) + self._from_mask(bear_mask, False)
        candles.sort(key=lambda c: c.x)

        merged: List[Candle] = []
        for c in candles:
            if not merged or abs(c.x - merged[-1].x) > 4:
                merged.append(c)
            elif abs(c.low - c.high) > abs(merged[-1].low - merged[-1].high):
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
            open_, close_ = (body_bottom, body_top) if is_bullish else (body_top, body_bottom)
            out.append(Candle(x=x + w // 2, open=open_, high=high, low=low, close=close_, is_bullish=is_bullish))
        return out


class PatternDetector:
    @staticmethod
    def detect(candles: List[Candle]) -> str:
        if len(candles) < 2:
            return "NONE"
        c, p = candles[-1], candles[-2]
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
    def __init__(self):
        self.templates = [self._small_body_template(), self._long_body_template(), self._doji_template()]

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

    @staticmethod
    def _doji_template() -> np.ndarray:
        img = np.zeros((20, 10), dtype=np.uint8)
        cv2.line(img, (5, 1), (5, 18), 255, 1)
        cv2.rectangle(img, (1, 9), (9, 11), 255, -1)
        return img

    def match_score(self, candle_patch: np.ndarray) -> float:
        if candle_patch.size == 0:
            return 0.0
        gray = cv2.cvtColor(candle_patch, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (10, 24))
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        best = 0.0
        for tpl in self.templates:
            tpl_resized = cv2.resize(tpl, (bw.shape[1], bw.shape[0]))
            best = max(best, float(cv2.matchTemplate(bw, tpl_resized, cv2.TM_CCOEFF_NORMED).max()))
        return best


class FeatureEngineer:
    @staticmethod
    def _ema(values: np.ndarray, period: int) -> float:
        if values.size == 0:
            return 0.0
        alpha = 2.0 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return float(ema)

    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        diffs = np.diff(closes[-(period + 1) :])
        gains = np.clip(diffs, 0, None)
        losses = np.abs(np.clip(diffs, None, 0))
        avg_gain = float(np.mean(gains))
        avg_loss = float(np.mean(losses))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    @staticmethod
    def build(candles: List[Candle], pattern: str, support: Optional[float], resistance: Optional[float], tpl_score: float) -> np.ndarray:
        if len(candles) < 8:
            return np.zeros(12, dtype=np.float32)

        closes = np.array([c.close for c in candles], dtype=np.float32)
        opens = np.array([c.open for c in candles], dtype=np.float32)
        highs = np.array([c.high for c in candles], dtype=np.float32)
        lows = np.array([c.low for c in candles], dtype=np.float32)

        ret1 = float(closes[-1] - closes[-2])
        ret3 = float(closes[-1] - closes[-4]) if len(closes) > 4 else ret1
        body = float(abs(closes[-1] - opens[-1]))
        range_last = float(max(1e-6, lows[-1] - highs[-1]))
        body_ratio = body / range_last

        ema_fast = FeatureEngineer._ema(closes[-15:], 5)
        ema_slow = FeatureEngineer._ema(closes[-30:], 12)
        ema_diff = ema_fast - ema_slow

        rsi = FeatureEngineer._rsi(closes)
        rsi_centered = (rsi - 50.0) / 50.0

        vol = float(np.std(np.diff(closes[-20:]))) if len(closes) > 20 else float(np.std(np.diff(closes)))
        trend_slope = float(np.polyfit(np.arange(min(20, len(closes))), closes[-min(20, len(closes)) :], 1)[0])

        support_dist = 0.0 if support is None else float(closes[-1] - support)
        resistance_dist = 0.0 if resistance is None else float(resistance - closes[-1])

        pattern_value = {
            "HAMMER": 0.5,
            "BULLISH_ENGULFING": 0.8,
            "BEARISH_ENGULFING": -0.8,
            "DOJI": 0.0,
            "NONE": 0.0,
        }.get(pattern, 0.0)

        feats = np.array(
            [
                ret1,
                ret3,
                body_ratio,
                ema_diff,
                rsi_centered,
                vol,
                trend_slope,
                support_dist,
                resistance_dist,
                pattern_value,
                tpl_score,
                1.0,
            ],
            dtype=np.float32,
        )

        scale = np.array([20, 30, 1, 20, 1, 15, 8, 30, 30, 1, 1, 1], dtype=np.float32)
        return np.clip(feats / scale, -3, 3)


class AdaptivePredictor:
    def __init__(self, cfg: dict):
        self.timeframe_seconds = int(cfg["chart"]["timeframe_seconds"])
        pcfg = cfg["prediction"]
        self.lr = float(pcfg.get("adaptive_learning_rate", 0.03))
        base_weights = pcfg.get(
            "feature_weights",
            [0.8, 0.6, 0.3, 0.9, 0.8, -0.2, 0.8, 0.3, -0.3, 0.7, 0.4, 0.0],
        )
        self.weights = np.array(base_weights, dtype=np.float32)
        self.bias = float(pcfg.get("model_bias", 0.0))
        self.pending: Deque[PendingPrediction] = deque(maxlen=20)
        self.recent_hits: Deque[int] = deque(maxlen=200)

    def _score(self, features: np.ndarray) -> float:
        raw = float(np.dot(self.weights, features) + self.bias)
        return float(np.tanh(raw))

    def predict(self, candles: List[Candle], features: np.ndarray, pattern: str) -> Prediction:
        if len(candles) < 8:
            eta = max(1, self.timeframe_seconds - int(time.time() % self.timeframe_seconds))
            return Prediction("CALL", 50.0, eta, pattern, "insufficient_data", 0.0)

        score = self._score(features)
        direction = "CALL" if score >= 0 else "PUT"

        model_conf = 50 + abs(score) * 40
        adaptive_acc = self.get_recent_accuracy()
        confidence = np.clip(model_conf * 0.7 + adaptive_acc * 30 * 0.3, 50, 99)

        eta = max(1, self.timeframe_seconds - int(time.time() % self.timeframe_seconds))
        reason = f"score={score:.2f},acc={adaptive_acc*100:.1f}%"

        self.pending.append(PendingPrediction(candle_index=len(candles), score=score, features=features.copy()))
        return Prediction(direction, float(round(confidence, 1)), eta, pattern, reason, score)

    def update_from_outcome(self, candles: List[Candle]):
        if len(candles) < 2 or not self.pending:
            return

        new_pending: Deque[PendingPrediction] = deque(maxlen=20)
        realized = 1.0 if candles[-1].close < candles[-2].close else -1.0

        for p in self.pending:
            if p.candle_index < len(candles):
                pred_label = 1.0 if p.score >= 0 else -1.0
                hit = int(pred_label == realized)
                self.recent_hits.append(hit)

                error = realized - pred_label
                self.weights = self.weights + self.lr * error * p.features
                self.bias = self.bias + self.lr * error * 0.1
            else:
                new_pending.append(p)

        self.pending = new_pending

    def get_recent_accuracy(self) -> float:
        if not self.recent_hits:
            return 0.5
        return float(np.mean(np.array(self.recent_hits, dtype=np.float32)))


class Logger:
    def __init__(self, enabled: bool, file_path: str):
        self.enabled = enabled
        self.path = Path(file_path)
        if self.enabled and not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    ["timestamp", "direction", "confidence", "eta", "pattern", "reason", "score", "recent_accuracy"]
                )

    def write(self, p: Prediction, recent_accuracy: float):
        if not self.enabled:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    datetime.utcnow().isoformat(),
                    p.direction,
                    p.confidence,
                    p.eta_seconds,
                    p.pattern,
                    p.reason,
                    p.score,
                    round(recent_accuracy * 100, 2),
                ]
            )


def select_chart_roi(frame: np.ndarray) -> Tuple[int, int, int, int]:
    print("Select chart area and press ENTER/SPACE.")
    roi = cv2.selectROI("Select Qxbroker Chart", frame, showCrosshair=True)
    cv2.destroyWindow("Select Qxbroker Chart")
    x, y, w, h = map(int, roi)
    if w <= 0 or h <= 0:
        raise RuntimeError("Invalid ROI selection")
    return x, y, w, h


def draw_overlay(frame: np.ndarray, pred: Prediction, sr: Tuple[Optional[float], Optional[float]], active: bool, recent_acc: float):
    support, resistance = sr
    out = frame.copy()
    _, w = out.shape[:2]
    cv2.rectangle(out, (0, 0), (w, 110), (15, 15, 15), -1)

    col = (80, 220, 80) if pred.direction == "CALL" else (80, 80, 220)
    cv2.putText(out, f"Status: {'RUNNING' if active else 'PAUSED'}", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1)
    cv2.putText(out, f"Signal: {pred.direction}  Confidence: {pred.confidence:.1f}%", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.63, col, 2)
    cv2.putText(out, f"Next candle: {pred.eta_seconds}s  Pattern: {pred.pattern}", (10, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (220, 220, 220), 1)
    cv2.putText(out, f"Adaptive accuracy (recent): {recent_acc*100:.1f}%  Score: {pred.score:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    cv2.putText(out, "Hotkeys: S pause | Q quit | L log | +/- alert", (10, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (170, 170, 170), 1)

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


def support_resistance(candles: List[Candle], lookback: int) -> Tuple[Optional[float], Optional[float]]:
    if not candles:
        return None, None
    sample = candles[-lookback:]
    return float(np.percentile([c.low for c in sample], 20)), float(np.percentile([c.high for c in sample], 80))


def main():
    cfg = load_config()
    web = QuotexWebApp(cfg)
    extractor = CandleExtractor(cfg)
    matcher = TemplateMatcher()
    predictor = AdaptivePredictor(cfg)
    logger = Logger(cfg["logging"]["enabled"], cfg["logging"]["file"])

    web.start()
    web.wait_for_manual_security_clear()
    input("After verification/login and chart visible, press ENTER...")

    x, y, w, h = select_chart_roi(web.capture_frame())
    active = True
    alert_threshold = int(cfg["prediction"]["min_confidence_alert"])
    last_alert_sec = -1

    while True:
        frame = web.capture_frame()
        chart = frame[y : y + h, x : x + w]
        pred = Prediction("CALL", 50.0, cfg["chart"]["timeframe_seconds"], "NONE", "paused", 0.0)
        sr = (None, None)

        if active:
            candles = extractor.extract(chart)
            predictor.update_from_outcome(candles)

            pattern = PatternDetector.detect(candles)
            sr = support_resistance(candles, cfg["prediction"]["support_resistance_lookback"])

            tpl_score = 0.0
            if candles:
                cx = int(np.clip(candles[-1].x, 8, chart.shape[1] - 8))
                tpl_score = matcher.match_score(chart[:, max(0, cx - 8) : min(chart.shape[1], cx + 8)])

            features = FeatureEngineer.build(candles, pattern, sr[0], sr[1], tpl_score)
            pred = predictor.predict(candles, features, pattern)

            recent_acc = predictor.get_recent_accuracy()
            logger.write(pred, recent_acc)

            now = int(time.time())
            if pred.confidence >= alert_threshold and now != last_alert_sec:
                beep()
                last_alert_sec = now
        else:
            recent_acc = predictor.get_recent_accuracy()

        cv2.imshow(cfg["ui"]["window_name"], draw_overlay(chart, pred, sr, active, recent_acc))
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("s"):
            active = not active
        if key in (ord("+"), ord("=")):
            alert_threshold = min(100, alert_threshold + 1)
        if key in (ord("-"), ord("_")):
            alert_threshold = max(0, alert_threshold - 1)
        if key == ord("l"):
            logger.enabled = not logger.enabled

    cv2.destroyAllWindows()
    web.close()


if __name__ == "__main__":
    main()
