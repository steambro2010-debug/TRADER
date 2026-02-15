import csv
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

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
class ExtractionStats:
    quality: float
    count: int
    spacing_cv: float


@dataclass
class SignalState:
    current_signal: str
    current_confidence: float
    next_signal: str
    next_confidence: float
    eta_seconds: int
    regime: str
    pattern: str
    quality: float
    should_trade: bool
    abstain_reason: str


@dataclass
class PendingSignal:
    candle_count: int
    direction: str
    regime: str


class QuotexWebApp:
    def __init__(self, cfg: dict):
        bcfg = cfg["browser"]
        self.url = bcfg["url"]
        self.user_data_dir = bcfg["user_data_dir"]
        self.viewport = bcfg["viewport"]
        self.channel = bcfg.get("channel", "chrome")
        self.slow_mo = int(bcfg.get("slow_mo_ms", 0))
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
        print("If security verification appears, solve it manually in browser.")
        markers = ["performing security verification", "verifies you are not a bot", "security service"]
        deadline = time.time() + self.security_timeout
        while time.time() < deadline:
            try:
                self.page.wait_for_timeout(1000)
                txt = self.page.inner_text("body").lower()[:5000]
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
            if any(m in txt for m in markers):
                continue
            return
        print("Verification timeout; continue once chart is visible.")

    def capture_frame(self) -> np.ndarray:
        assert self.page is not None
        png = self.page.screenshot(full_page=False)
        return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)

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

    def extract(self, roi: np.ndarray) -> Tuple[List[Candle], ExtractionStats]:
        # conservative denoising for stable extraction
        blur = cv2.GaussianBlur(roi, (3, 3), 0)
        bull_mask = cv2.inRange(blur, self.bull_min, self.bull_max)
        bear_mask = cv2.inRange(blur, self.bear_min, self.bear_max)

        kernel = np.ones((3, 3), np.uint8)
        bull_mask = cv2.morphologyEx(bull_mask, cv2.MORPH_OPEN, kernel)
        bull_mask = cv2.morphologyEx(bull_mask, cv2.MORPH_CLOSE, kernel)
        bear_mask = cv2.morphologyEx(bear_mask, cv2.MORPH_OPEN, kernel)
        bear_mask = cv2.morphologyEx(bear_mask, cv2.MORPH_CLOSE, kernel)

        candles = self._from_mask(bull_mask, True) + self._from_mask(bear_mask, False)
        candles.sort(key=lambda x: x.x)
        merged = self._merge_close_columns(candles)
        merged = merged[-self.max_candles :]
        return merged, self._quality_metrics(merged)

    def _from_mask(self, mask: np.ndarray, is_bullish: bool) -> List[Candle]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out: List[Candle] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 3 or h < 8:
                continue
            high = float(y)
            low = float(y + h)
            # less biased body approximation: use mask density near center
            body_h = max(2, int(h * 0.45))
            mid = y + h // 2
            body_top = float(max(y, mid - body_h // 2))
            body_bottom = float(min(y + h, mid + body_h // 2))
            open_, close_ = (body_bottom, body_top) if is_bullish else (body_top, body_bottom)
            out.append(Candle(x=x + w // 2, open=open_, high=high, low=low, close=close_, is_bullish=is_bullish))
        return out

    @staticmethod
    def _merge_close_columns(candles: List[Candle]) -> List[Candle]:
        merged: List[Candle] = []
        for c in candles:
            if not merged or abs(c.x - merged[-1].x) > 4:
                merged.append(c)
            else:
                # keep taller candidate for wick coverage
                prev = merged[-1]
                if abs(c.low - c.high) > abs(prev.low - prev.high):
                    merged[-1] = c
        return merged

    @staticmethod
    def _quality_metrics(candles: List[Candle]) -> ExtractionStats:
        if len(candles) < 12:
            return ExtractionStats(quality=0.0, count=len(candles), spacing_cv=9.9)

        xs = np.array([c.x for c in candles], dtype=np.float32)
        spacing = np.diff(xs)
        spacing = spacing[spacing > 0]
        if spacing.size == 0:
            return ExtractionStats(quality=0.0, count=len(candles), spacing_cv=9.9)

        spacing_cv = float(np.std(spacing) / max(1e-6, np.mean(spacing)))
        body_ratios = []
        for c in candles[-40:]:
            rng = max(1e-6, c.low - c.high)
            body_ratios.append(abs(c.close - c.open) / rng)
        body_consistency = float(np.clip(1.0 - np.std(body_ratios), 0.0, 1.0))

        count_score = float(np.clip((len(candles) - 20) / 80.0, 0.0, 1.0))
        spacing_score = float(np.clip(1.0 - spacing_cv, 0.0, 1.0))
        quality = 0.45 * count_score + 0.35 * spacing_score + 0.20 * body_consistency
        return ExtractionStats(quality=float(np.clip(quality, 0.0, 1.0)), count=len(candles), spacing_cv=spacing_cv)


class PatternDetector:
    @staticmethod
    def detect(candles: List[Candle]) -> str:
        if len(candles) < 2:
            return "NONE"
        c, p = candles[-1], candles[-2]
        body = abs(c.close - c.open)
        wick = abs(c.low - c.high)
        if wick > 0 and body / wick < 0.12:
            return "DOJI"

        p_top, p_bottom = min(p.open, p.close), max(p.open, p.close)
        c_top, c_bottom = min(c.open, c.close), max(c.open, c.close)
        if (not p.is_bullish) and c.is_bullish and c_top <= p_top and c_bottom >= p_bottom:
            return "BULL_ENG"
        if p.is_bullish and (not c.is_bullish) and c_top <= p_top and c_bottom >= p_bottom:
            return "BEAR_ENG"
        return "NONE"


def support_resistance(candles: List[Candle], lookback: int) -> Tuple[Optional[float], Optional[float]]:
    if not candles:
        return None, None
    sample = candles[-lookback:]
    lows = [c.low for c in sample]
    highs = [c.high for c in sample]
    return float(np.percentile(lows, 20)), float(np.percentile(highs, 80))


class RegimeClassifier:
    @staticmethod
    def classify(candles: List[Candle]) -> str:
        if len(candles) < 40:
            return "unknown"
        closes = np.array([c.close for c in candles[-40:]], dtype=np.float32)
        slope = float(np.polyfit(np.arange(len(closes), dtype=np.float32), closes, 1)[0])
        vol = float(np.std(np.diff(closes[-20:])))
        movement = float(abs(closes[-1] - closes[0]))

        trend_strength = movement / max(1e-6, vol * 20)
        if vol > 7.0:
            return "volatile"
        if trend_strength > 1.15:
            return "trend_up" if slope < 0 else "trend_down"
        return "range"


class LeanFeatureEngineer:
    DIM = 12

    @staticmethod
    def _atr(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0.0
        tr = []
        closes = np.array([c.close for c in candles], dtype=np.float32)
        highs = np.array([c.high for c in candles], dtype=np.float32)
        lows = np.array([c.low for c in candles], dtype=np.float32)
        for i in range(-period, 0):
            prev_close = closes[i - 1]
            tr.append(max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close)))
        return float(np.mean(tr))

    @staticmethod
    def build(candles: List[Candle], support: Optional[float], resistance: Optional[float], pattern: str) -> np.ndarray:
        if len(candles) < 40:
            return np.zeros(LeanFeatureEngineer.DIM, dtype=np.float32)

        closes = np.array([c.close for c in candles], dtype=np.float32)
        opens = np.array([c.open for c in candles], dtype=np.float32)
        highs = np.array([c.high for c in candles], dtype=np.float32)
        lows = np.array([c.low for c in candles], dtype=np.float32)

        ret1 = closes[-1] - closes[-2]
        ret3 = closes[-1] - closes[-4]
        ret6 = closes[-1] - closes[-7]
        vol10 = float(np.std(np.diff(closes[-10:])))
        vol30 = float(np.std(np.diff(closes[-30:])))

        x = np.arange(20, dtype=np.float32)
        y = closes[-20:]
        slope = float(np.polyfit(x, y, 1)[0])
        y_hat = slope * x + float(np.mean(y))
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2)) + 1e-6
        r2 = float(np.clip(1 - ss_res / ss_tot, 0, 1))

        atr = LeanFeatureEngineer._atr(candles, 14)
        rng = max(1e-6, lows[-1] - highs[-1])
        body_ratio = abs(closes[-1] - opens[-1]) / rng

        s_dist = 0.0 if support is None else closes[-1] - support
        r_dist = 0.0 if resistance is None else resistance - closes[-1]
        bull_ratio = float(np.mean([1.0 if c.is_bullish else 0.0 for c in candles[-10:]]))
        pattern_val = {"BULL_ENG": 1.0, "BEAR_ENG": -1.0, "DOJI": 0.0, "NONE": 0.0}.get(pattern, 0.0)

        feats = np.array(
            [ret1, ret3, ret6, vol10, vol30, slope, r2, atr, body_ratio, s_dist, r_dist, bull_ratio + pattern_val * 0.15],
            dtype=np.float32,
        )
        scales = np.array([20, 25, 30, 8, 12, 8, 1, 20, 1, 30, 30, 1], dtype=np.float32)
        return np.clip(feats / scales, -3, 3)


class LeanSignalModel:
    def __init__(self, cfg: dict):
        m = cfg["model"]
        p = cfg["prediction"]
        self.temperature = float(m.get("logit_temperature", 1.5))
        self.bias = p.get("model_bias_by_regime", {})
        self.weights = m.get("weights", {})

    def _params(self, regime: str) -> Tuple[np.ndarray, float]:
        w = self.weights.get(regime) or self.weights.get("default") or [0.0] * LeanFeatureEngineer.DIM
        b = float(self.bias.get(regime, self.bias.get("default", 0.0)))
        w_arr = np.array(w, dtype=np.float32)
        if w_arr.size != LeanFeatureEngineer.DIM:
            w_arr = np.resize(w_arr, LeanFeatureEngineer.DIM).astype(np.float32)
        return w_arr, b

    def predict(self, candles: List[Candle], feats: np.ndarray, regime: str) -> Tuple[str, float, str, float, int]:
        tf = 60
        if len(candles) > 0:
            tf = max(1, int(abs(candles[-1].x - candles[-2].x)) if len(candles) > 2 else 60)
        eta = max(1, 60 - int(time.time() % 60))

        w, b = self._params(regime)
        raw = float(np.dot(w, feats) + b)
        z = np.clip(raw / max(1e-6, self.temperature), -8, 8)
        p_up = 1.0 / (1.0 + np.exp(-z))

        next_signal = "CALL" if p_up >= 0.5 else "PUT"
        next_conf = float(max(p_up, 1 - p_up) * 100)

        # current signal from short-term momentum only, to avoid pseudo precision
        if len(candles) >= 3:
            micro = (candles[-1].close - candles[-2].close) + 0.4 * (candles[-2].close - candles[-3].close)
            current_signal = "CALL" if micro >= 0 else "PUT"
            current_conf = float(np.clip(50 + min(45, abs(micro) * 3.2), 50, 95))
        else:
            current_signal, current_conf = "WAIT", 50.0

        return current_signal, current_conf, next_signal, next_conf, eta


class AbstentionGate:
    def __init__(self, cfg: dict):
        p = cfg["prediction"]
        self.min_quality = float(p.get("min_extraction_quality", 0.72))
        self.allow_volatile = bool(p.get("allow_volatile_regime", False))
        self.thresholds = p.get(
            "confidence_threshold_by_regime",
            {"trend_up": 66.0, "trend_down": 66.0, "range": 72.0, "volatile": 82.0, "unknown": 85.0},
        )
        self.min_candles = int(p.get("min_candles_required", 60))

    def decide(self, candles: List[Candle], quality: float, regime: str, next_conf: float) -> Tuple[bool, str]:
        if len(candles) < self.min_candles:
            return False, "insufficient_history"
        if quality < self.min_quality:
            return False, "low_extraction_quality"
        if regime == "volatile" and not self.allow_volatile:
            return False, "volatile_regime_blocked"
        threshold = float(self.thresholds.get(regime, self.thresholds.get("unknown", 85.0)))
        if next_conf < threshold:
            return False, f"confidence<{threshold:.1f}"
        return True, "ok"


class PerformanceGuard:
    def __init__(self, cfg: dict):
        r = cfg.get("risk", {})
        self.max_consecutive_losses = int(r.get("max_consecutive_losses", 4))
        self.min_win_rate = float(r.get("min_shadow_win_rate", 0.52))
        self.window = int(r.get("shadow_window", 80))
        self.pending: Deque[PendingSignal] = deque(maxlen=200)
        self.outcomes: Deque[int] = deque(maxlen=self.window)
        self.by_regime: Dict[str, Deque[int]] = {
            "trend_up": deque(maxlen=self.window),
            "trend_down": deque(maxlen=self.window),
            "range": deque(maxlen=self.window),
            "volatile": deque(maxlen=self.window),
            "unknown": deque(maxlen=self.window),
        }

    def register(self, candle_count: int, direction: str, regime: str):
        self.pending.append(PendingSignal(candle_count=candle_count, direction=direction, regime=regime))

    def resolve(self, candles: List[Candle]):
        if len(candles) < 2 or not self.pending:
            return
        realized = "CALL" if candles[-1].close < candles[-2].close else "PUT"

        keep: Deque[PendingSignal] = deque(maxlen=200)
        for p in self.pending:
            if p.candle_count < len(candles):
                hit = 1 if p.direction == realized else 0
                self.outcomes.append(hit)
                self.by_regime.setdefault(p.regime, deque(maxlen=self.window)).append(hit)
            else:
                keep.append(p)
        self.pending = keep

    def win_rate(self) -> float:
        if not self.outcomes:
            return 0.5
        return float(np.mean(np.array(self.outcomes, dtype=np.float32)))

    def consecutive_losses(self) -> int:
        c = 0
        for x in reversed(self.outcomes):
            if x == 0:
                c += 1
            else:
                break
        return c

    def should_pause(self) -> Tuple[bool, str]:
        if len(self.outcomes) < 20:
            return False, "warming_up"
        if self.consecutive_losses() >= self.max_consecutive_losses:
            return True, "consecutive_loss_guard"
        if self.win_rate() < self.min_win_rate:
            return True, "shadow_win_rate_guard"
        return False, "ok"


class Logger:
    def __init__(self, enabled: bool, path: str):
        self.enabled = enabled
        self.path = Path(path)
        if self.enabled and not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    [
                        "ts",
                        "current_signal",
                        "current_conf",
                        "next_signal",
                        "next_conf",
                        "regime",
                        "quality",
                        "should_trade",
                        "abstain_reason",
                        "shadow_win_rate",
                    ]
                )

    def write(self, s: SignalState, win_rate: float):
        if not self.enabled:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    datetime.utcnow().isoformat(),
                    s.current_signal,
                    round(s.current_confidence, 2),
                    s.next_signal,
                    round(s.next_confidence, 2),
                    s.regime,
                    round(s.quality, 4),
                    s.should_trade,
                    s.abstain_reason,
                    round(win_rate, 4),
                ]
            )


def select_chart_roi(frame: np.ndarray) -> Tuple[int, int, int, int]:
    print("Select chart area and press ENTER/SPACE")
    roi = cv2.selectROI("Select Qxbroker Chart", frame, showCrosshair=True)
    cv2.destroyWindow("Select Qxbroker Chart")
    x, y, w, h = map(int, roi)
    if w <= 0 or h <= 0:
        raise RuntimeError("Invalid ROI selection")
    return x, y, w, h


def draw_overlay(frame: np.ndarray, state: SignalState, stats: ExtractionStats, guard: PerformanceGuard, active: bool, alert_threshold: int) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]

    cv2.rectangle(out, (0, 0), (w, 165), (12, 15, 20), -1)
    cv2.rectangle(out, (0, 0), (w, 165), (50, 55, 60), 1)

    status_col = (90, 220, 90) if active else (100, 120, 220)
    cv2.putText(out, f"STATUS: {'RUNNING' if active else 'PAUSED'}", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_col, 2)

    cv2.rectangle(out, (10, 35), (w // 2 - 8, 102), (24, 30, 40), -1)
    cv2.rectangle(out, (10, 35), (w // 2 - 8, 102), (65, 70, 80), 1)
    cur_col = (80, 220, 80) if state.current_signal == "CALL" else (90, 140, 255)
    cv2.putText(out, "CURRENT", (20, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (225, 225, 225), 1)
    cv2.putText(out, f"{state.current_signal} {state.current_confidence:.1f}%", (20, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.78, cur_col, 2)

    cv2.rectangle(out, (w // 2 + 8, 35), (w - 10, 102), (24, 30, 40), -1)
    cv2.rectangle(out, (w // 2 + 8, 35), (w - 10, 102), (65, 70, 80), 1)
    next_col = (80, 220, 80) if state.next_signal == "CALL" else (90, 140, 255)
    cv2.putText(out, "NEXT", (w // 2 + 18, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (225, 225, 225), 1)
    cv2.putText(out, f"{state.next_signal} {state.next_confidence:.1f}% ETA:{state.eta_seconds}s", (w // 2 + 18, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.66, next_col, 2)

    decision = "TRADE" if state.should_trade else f"ABSTAIN ({state.abstain_reason})"
    dec_col = (90, 225, 120) if state.should_trade else (130, 170, 255)
    cv2.putText(out, f"Decision: {decision}", (12, 123), cv2.FONT_HERSHEY_SIMPLEX, 0.56, dec_col, 2)
    cv2.putText(
        out,
        f"Regime:{state.regime} | Quality:{state.quality:.2f} | Candles:{stats.count} | SpacingCV:{stats.spacing_cv:.2f} | ShadowWR:{guard.win_rate()*100:.1f}% | Alert>={alert_threshold}%",
        (12, 145),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (190, 195, 205),
        1,
    )
    cv2.putText(out, "Hotkeys: S pause  Q quit  L log  +/- alert", (12, 161), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (165, 170, 180), 1)

    bar_h = max(1, int((state.next_confidence / 100.0) * (h - 190)))
    cv2.rectangle(out, (w - 22, h - 10 - bar_h), (w - 12, h - 10), next_col, -1)
    cv2.rectangle(out, (w - 22, 175), (w - 12, h - 10), (80, 80, 90), 1)

    return out


def beep():
    try:
        import winsound

        winsound.Beep(1200, 120)
    except Exception:
        print("\a", end="")


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Missing config.yaml. Copy config.example.yaml to config.yaml first.")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    web = QuotexWebApp(cfg)
    extractor = CandleExtractor(cfg)
    model = LeanSignalModel(cfg)
    gate = AbstentionGate(cfg)
    guard = PerformanceGuard(cfg)
    logger = Logger(cfg["logging"]["enabled"], cfg["logging"]["file"])

    web.start()
    web.wait_for_manual_security_clear()
    input("After verification/login and chart visible, press ENTER...")

    x, y, w, h = select_chart_roi(web.capture_frame())
    active = True
    alert_threshold = int(cfg["prediction"]["min_confidence_alert"])
    last_alert = -1

    while True:
        frame = web.capture_frame()
        chart = frame[y : y + h, x : x + w]
        candles, stats = extractor.extract(chart)
        guard.resolve(candles)

        pattern = PatternDetector.detect(candles)
        sr = support_resistance(candles, int(cfg["prediction"]["support_resistance_lookback"]))
        regime = RegimeClassifier.classify(candles)
        feats = LeanFeatureEngineer.build(candles, sr[0], sr[1], pattern)

        current_signal, current_conf, next_signal, next_conf, eta = model.predict(candles, feats, regime)
        should_trade, reason = gate.decide(candles, stats.quality, regime, next_conf)

        state = SignalState(
            current_signal=current_signal,
            current_confidence=current_conf,
            next_signal=next_signal,
            next_confidence=next_conf,
            eta_seconds=eta,
            regime=regime,
            pattern=pattern,
            quality=stats.quality,
            should_trade=bool(active and should_trade),
            abstain_reason=reason if active else "paused",
        )

        if active and should_trade:
            guard.register(len(candles), next_signal, regime)
            now = int(time.time())
            if next_conf >= alert_threshold and now != last_alert:
                beep()
                last_alert = now

        pause, pause_reason = guard.should_pause()
        if active and pause:
            active = False
            print(f"Auto-paused by guard: {pause_reason}")

        logger.write(state, guard.win_rate())

        shown = draw_overlay(chart, state, stats, guard, active, alert_threshold)
        cv2.imshow(cfg["ui"]["window_name"], shown)

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
