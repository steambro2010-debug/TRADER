import csv
import hashlib
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
class SignalState:
    current_signal: str
    current_confidence: float
    next_signal: str
    next_confidence: float
    eta_seconds: int
    pattern: str
    score: float
    reason: str


@dataclass
class PendingPrediction:
    candle_index: int
    pred_sign: float
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

            if any(marker in text for marker in markers):
                continue
            return

        print("Verification timeout reached; continue manually once chart is visible.")

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

    def extract(self, roi: np.ndarray) -> List[Candle]:
        bull_mask = cv2.inRange(roi, self.bull_min, self.bull_max)
        bear_mask = cv2.inRange(roi, self.bear_min, self.bear_max)
        kernel = np.ones((3, 3), np.uint8)
        bull_mask = cv2.morphologyEx(bull_mask, cv2.MORPH_OPEN, kernel)
        bear_mask = cv2.morphologyEx(bear_mask, cv2.MORPH_OPEN, kernel)

        candles = self._from_mask(bull_mask, True) + self._from_mask(bear_mask, False)
        candles.sort(key=lambda x: x.x)

        merged: List[Candle] = []
        for c in candles:
            if not merged or abs(c.x - merged[-1].x) > 4:
                merged.append(c)
            elif abs(c.low - c.high) > abs(merged[-1].low - merged[-1].high):
                merged[-1] = c
        return merged[-self.max_candles :]

    def _from_mask(self, mask: np.ndarray, is_bullish: bool) -> List[Candle]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result: List[Candle] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 3 or h < 8:
                continue
            high = float(y)
            low = float(y + h)
            body_top = float(y + h * 0.25)
            body_bottom = float(y + h * 0.75)
            open_, close_ = (body_bottom, body_top) if is_bullish else (body_top, body_bottom)
            result.append(Candle(x=x + w // 2, open=open_, high=high, low=low, close=close_, is_bullish=is_bullish))
        return result


class PatternDetector:
    @staticmethod
    def detect(candles: List[Candle]) -> str:
        if len(candles) < 2:
            return "NONE"
        c = candles[-1]
        p = candles[-2]
        body = abs(c.close - c.open)
        wick_total = abs(c.low - c.high)
        upper_wick = max(0.0, min(c.open, c.close) - c.high)
        lower_wick = max(0.0, c.low - max(c.open, c.close))

        if wick_total > 0 and body / wick_total < 0.14:
            return "DOJI"
        if lower_wick > body * 2 and upper_wick < body * 0.6:
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
        self.templates = [self._doji(), self._small_body(), self._long_body(), self._hammer()]

    def _doji(self) -> np.ndarray:
        img = np.zeros((22, 12), dtype=np.uint8)
        cv2.line(img, (6, 1), (6, 20), 255, 1)
        cv2.rectangle(img, (2, 10), (10, 12), 255, -1)
        return img

    def _small_body(self) -> np.ndarray:
        img = np.zeros((22, 12), dtype=np.uint8)
        cv2.line(img, (6, 1), (6, 20), 255, 1)
        cv2.rectangle(img, (3, 8), (9, 14), 255, -1)
        return img

    def _long_body(self) -> np.ndarray:
        img = np.zeros((24, 12), dtype=np.uint8)
        cv2.line(img, (6, 1), (6, 22), 255, 1)
        cv2.rectangle(img, (2, 3), (10, 20), 255, -1)
        return img

    def _hammer(self) -> np.ndarray:
        img = np.zeros((24, 12), dtype=np.uint8)
        cv2.line(img, (6, 2), (6, 23), 255, 1)
        cv2.rectangle(img, (3, 4), (9, 10), 255, -1)
        return img

    def match_score(self, patch: np.ndarray) -> float:
        if patch.size == 0:
            return 0.0
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (12, 24))
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        best = 0.0
        for tpl in self.templates:
            tpl_r = cv2.resize(tpl, (bw.shape[1], bw.shape[0]))
            best = max(best, float(cv2.matchTemplate(bw, tpl_r, cv2.TM_CCOEFF_NORMED).max()))
        return best


class FeatureEngineer:
    FEATURE_DIM = 36

    @staticmethod
    def _ema(arr: np.ndarray, period: int) -> float:
        if arr.size == 0:
            return 0.0
        alpha = 2.0 / (period + 1)
        ema = float(arr[0])
        for x in arr[1:]:
            ema = alpha * float(x) + (1 - alpha) * ema
        return ema

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
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def _stochastic(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, period: int = 14) -> float:
        if len(closes) < period:
            return 50.0
        c = float(closes[-1])
        hh = float(np.max(highs[-period:]))
        ll = float(np.min(lows[-period:]))
        if hh - ll == 0:
            return 50.0
        return 100 * (c - ll) / (hh - ll)

    @staticmethod
    def _cci(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, period: int = 20) -> float:
        if len(closes) < period:
            return 0.0
        tp = (highs + lows + closes) / 3.0
        ma = np.mean(tp[-period:])
        dev = np.mean(np.abs(tp[-period:] - ma))
        if dev == 0:
            return 0.0
        return float((tp[-1] - ma) / (0.015 * dev))

    @staticmethod
    def _atr(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(-period, 0):
            prev_close = closes[i - 1]
            tr = max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))
            trs.append(tr)
        return float(np.mean(trs))

    @staticmethod
    def _macd(closes: np.ndarray) -> Tuple[float, float, float]:
        ema12 = FeatureEngineer._ema(closes[-60:], 12)
        ema26 = FeatureEngineer._ema(closes[-60:], 26)
        macd = ema12 - ema26
        signal = macd * 0.8
        hist = macd - signal
        return macd, signal, hist

    @staticmethod
    def build(candles: List[Candle], pattern: str, support: Optional[float], resistance: Optional[float], tpl_score: float) -> np.ndarray:
        if len(candles) < 12:
            return np.zeros(FeatureEngineer.FEATURE_DIM, dtype=np.float32)

        closes = np.array([c.close for c in candles], dtype=np.float32)
        opens = np.array([c.open for c in candles], dtype=np.float32)
        highs = np.array([c.high for c in candles], dtype=np.float32)
        lows = np.array([c.low for c in candles], dtype=np.float32)

        ret1 = closes[-1] - closes[-2]
        ret2 = closes[-1] - closes[-3]
        ret3 = closes[-1] - closes[-4]
        ret5 = closes[-1] - closes[-6]
        ret8 = closes[-1] - closes[-9]
        velocity = ret1 - (closes[-2] - closes[-3])

        body = abs(closes[-1] - opens[-1])
        span = max(1e-6, lows[-1] - highs[-1])
        body_ratio = body / span
        upper = max(0.0, min(opens[-1], closes[-1]) - highs[-1])
        lower = max(0.0, lows[-1] - max(opens[-1], closes[-1]))

        ema5 = FeatureEngineer._ema(closes[-20:], 5)
        ema8 = FeatureEngineer._ema(closes[-30:], 8)
        ema13 = FeatureEngineer._ema(closes[-40:], 13)
        ema21 = FeatureEngineer._ema(closes[-60:], 21)
        ema_spread1 = ema5 - ema13
        ema_spread2 = ema8 - ema21

        rsi = FeatureEngineer._rsi(closes)
        stoch = FeatureEngineer._stochastic(closes, highs, lows)
        cci = FeatureEngineer._cci(closes, highs, lows)
        atr = FeatureEngineer._atr(closes, highs, lows)
        macd, macd_signal, macd_hist = FeatureEngineer._macd(closes)

        rolling_std10 = float(np.std(np.diff(closes[-10:])))
        rolling_std20 = float(np.std(np.diff(closes[-20:])))
        slope10 = float(np.polyfit(np.arange(10), closes[-10:], 1)[0])
        slope20 = float(np.polyfit(np.arange(20), closes[-20:], 1)[0])

        bb_mid = float(np.mean(closes[-20:]))
        bb_std = float(np.std(closes[-20:]))
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_pos = 0.0 if bb_upper == bb_lower else (closes[-1] - bb_lower) / (bb_upper - bb_lower)

        support_dist = 0.0 if support is None else closes[-1] - support
        resistance_dist = 0.0 if resistance is None else resistance - closes[-1]

        bull_count_5 = float(np.mean([1.0 if c.is_bullish else 0.0 for c in candles[-5:]]))
        bull_count_10 = float(np.mean([1.0 if c.is_bullish else 0.0 for c in candles[-10:]]))
        range_ratio_5_20 = float(np.mean(lows[-5:] - highs[-5:]) / max(1e-6, np.mean(lows[-20:] - highs[-20:])))

        pattern_val = {
            "HAMMER": 0.4,
            "BULLISH_ENGULFING": 0.8,
            "BEARISH_ENGULFING": -0.8,
            "DOJI": 0.0,
            "NONE": 0.0,
        }.get(pattern, 0.0)

        feats = np.array(
            [
                ret1,
                ret2,
                ret3,
                ret5,
                ret8,
                velocity,
                body_ratio,
                upper,
                lower,
                ema_spread1,
                ema_spread2,
                rsi,
                stoch,
                cci,
                atr,
                macd,
                macd_signal,
                macd_hist,
                rolling_std10,
                rolling_std20,
                slope10,
                slope20,
                bb_pos,
                support_dist,
                resistance_dist,
                bull_count_5,
                bull_count_10,
                range_ratio_5_20,
                float(tpl_score),
                pattern_val,
                float(closes[-1] - opens[-1]),
                float(lows[-1] - highs[-1]),
                float(np.mean(np.diff(closes[-6:]))),
                float(np.mean(np.diff(closes[-12:]))),
                float(np.mean(np.diff(closes[-24:]))),
                1.0,
            ],
            dtype=np.float32,
        )

        scales = np.array(
            [
                20,
                20,
                25,
                30,
                35,
                10,
                1,
                20,
                20,
                20,
                20,
                100,
                100,
                250,
                30,
                20,
                20,
                10,
                10,
                12,
                8,
                8,
                1,
                30,
                30,
                1,
                1,
                2,
                1,
                1,
                20,
                30,
                8,
                8,
                8,
                1,
            ],
            dtype=np.float32,
        )
        return np.clip(feats / scales, -3.5, 3.5)


class HeavyLocalModel:
    """Local hybrid model with optional ~5GB memory bank on disk (memmap)."""

    def __init__(self, cfg: dict):
        pcfg = cfg["prediction"]
        mcfg = cfg.get("model", {})
        self.feature_dim = FeatureEngineer.FEATURE_DIM
        self.timeframe_seconds = int(cfg["chart"]["timeframe_seconds"])
        self.lr = float(pcfg.get("adaptive_learning_rate", 0.02))
        self.bias = float(pcfg.get("model_bias", 0.0))

        self.w_linear = np.array(pcfg.get("feature_weights", [0.1] * self.feature_dim), dtype=np.float32)
        if self.w_linear.size != self.feature_dim:
            self.w_linear = np.resize(self.w_linear, self.feature_dim).astype(np.float32)

        self.hidden = int(mcfg.get("hidden_dim", 512))
        self.sample_bank_rows = int(mcfg.get("memory_sample_rows", 4096))
        self.pending: Deque[PendingPrediction] = deque(maxlen=100)
        self.recent_hits: Deque[int] = deque(maxlen=500)

        seed = int(mcfg.get("seed", 42))
        rng = np.random.default_rng(seed)
        self.w1 = rng.normal(0, 0.06, size=(self.feature_dim, self.hidden)).astype(np.float32)
        self.w2 = rng.normal(0, 0.06, size=(self.hidden, 1)).astype(np.float32)

        self.memmap_path: Optional[Path] = None
        self.memmap_rows = 0
        self.memmap = None
        if bool(mcfg.get("enable_heavy_memory_bank", True)):
            self._init_memory_bank(mcfg)

    def _init_memory_bank(self, mcfg: dict):
        model_dir = Path(mcfg.get("model_dir", "./local_model"))
        model_dir.mkdir(parents=True, exist_ok=True)
        target_gb = float(mcfg.get("target_size_gb", 5.0))
        dtype_bytes = 4
        rows = int((target_gb * (1024**3)) / (self.feature_dim * dtype_bytes))
        rows = max(rows, 10000)

        self.memmap_path = model_dir / f"heavy_bank_{rows}x{self.feature_dim}.f32"
        total_bytes = rows * self.feature_dim * dtype_bytes

        if not self.memmap_path.exists() or self.memmap_path.stat().st_size != total_bytes:
            print(f"Preparing heavy local memory bank at {self.memmap_path} (~{target_gb:.2f} GB)...")
            mm = np.memmap(self.memmap_path, mode="w+", dtype=np.float32, shape=(rows, self.feature_dim))
            # deterministic pseudo-random fill in chunks, avoids full RAM load
            chunk = 4096
            for i in range(0, rows, chunk):
                n = min(chunk, rows - i)
                row_ids = np.arange(i, i + n, dtype=np.float32).reshape(-1, 1)
                col_ids = np.arange(self.feature_dim, dtype=np.float32).reshape(1, -1)
                block = np.sin(row_ids * 0.013 + col_ids * 0.17).astype(np.float32)
                mm[i : i + n] = block
            mm.flush()
            del mm

        self.memmap_rows = rows
        self.memmap = np.memmap(self.memmap_path, mode="r+", dtype=np.float32, shape=(rows, self.feature_dim))

    def _hash_index(self, vec: np.ndarray) -> int:
        h = hashlib.blake2b(vec.tobytes(), digest_size=8).digest()
        return int.from_bytes(h, "little") % max(1, self.memmap_rows)

    def _deep_score(self, x: np.ndarray) -> float:
        hidden = np.tanh(x @ self.w1)
        out = float(np.tanh(hidden @ self.w2)[0])
        return out

    def _memory_score(self, x: np.ndarray) -> float:
        if self.memmap is None:
            return 0.0
        center = self._hash_index(x)
        half = self.sample_bank_rows // 2
        start = max(0, center - half)
        end = min(self.memmap_rows, start + self.sample_bank_rows)
        bank = self.memmap[start:end]
        sims = bank @ x
        k = min(16, len(sims))
        idx = np.argpartition(sims, -k)[-k:]
        top = sims[idx]
        return float(np.tanh(np.mean(top)))

    def _score(self, x: np.ndarray) -> float:
        linear = float(np.tanh(np.dot(self.w_linear, x) + self.bias))
        deep = self._deep_score(x)
        memory = self._memory_score(x)
        return float(np.clip(0.40 * linear + 0.35 * deep + 0.25 * memory, -1.0, 1.0))

    def predict(self, candles: List[Candle], features: np.ndarray, pattern: str) -> SignalState:
        eta = max(1, self.timeframe_seconds - int(time.time() % self.timeframe_seconds))
        if len(candles) < 12:
            return SignalState("WAIT", 50.0, "WAIT", 50.0, eta, pattern, 0.0, "insufficient_data")

        score = self._score(features)
        next_signal = "CALL" if score >= 0 else "PUT"
        next_conf = float(np.clip(50 + abs(score) * 45 + self.get_recent_accuracy() * 8, 50, 99))

        # current signal = momentum of forming/last visible candle + model blend
        micro = 0.0
        if len(candles) >= 3:
            micro = (candles[-1].close - candles[-2].close) + 0.5 * (candles[-2].close - candles[-3].close)
        current_score = np.tanh(0.7 * score + 0.3 * (micro / 10.0))
        current_signal = "CALL" if current_score >= 0 else "PUT"
        current_conf = float(np.clip(50 + abs(current_score) * 40, 50, 95))

        self.pending.append(PendingPrediction(candle_index=len(candles), pred_sign=1.0 if score >= 0 else -1.0, features=features.copy()))
        reason = f"S={score:.2f}|acc={self.get_recent_accuracy()*100:.1f}%"
        return SignalState(current_signal, current_conf, next_signal, next_conf, eta, pattern, float(score), reason)

    def update_from_outcome(self, candles: List[Candle]):
        if len(candles) < 2 or not self.pending:
            return

        realized = 1.0 if candles[-1].close < candles[-2].close else -1.0
        keep: Deque[PendingPrediction] = deque(maxlen=100)

        for p in self.pending:
            if p.candle_index < len(candles):
                hit = int(p.pred_sign == realized)
                self.recent_hits.append(hit)
                err = realized - p.pred_sign

                self.w_linear += self.lr * err * p.features
                self.bias += self.lr * err * 0.05

                # lightweight online backprop for deep head
                hidden = np.tanh(p.features @ self.w1)
                grad_out = err * (1.0 - (hidden @ self.w2)[0] ** 2)
                self.w2 += self.lr * grad_out * hidden.reshape(-1, 1)
                grad_hidden = (self.w2[:, 0] * grad_out) * (1 - hidden**2)
                self.w1 += self.lr * np.outer(p.features, grad_hidden)

                if self.memmap is not None:
                    idx = self._hash_index(p.features)
                    self.memmap[idx] = 0.995 * self.memmap[idx] + 0.005 * (realized * p.features)
            else:
                keep.append(p)
        self.pending = keep

    def get_recent_accuracy(self) -> float:
        if not self.recent_hits:
            return 0.5
        return float(np.mean(np.array(self.recent_hits, dtype=np.float32)))


def support_resistance(candles: List[Candle], lookback: int) -> Tuple[Optional[float], Optional[float]]:
    if not candles:
        return None, None
    sample = candles[-lookback:]
    lows = [c.low for c in sample]
    highs = [c.high for c in sample]
    return float(np.percentile(lows, 20)), float(np.percentile(highs, 80))


class Logger:
    def __init__(self, enabled: bool, file_path: str):
        self.enabled = enabled
        self.path = Path(file_path)
        if self.enabled and not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    [
                        "timestamp",
                        "current_signal",
                        "current_confidence",
                        "next_signal",
                        "next_confidence",
                        "eta_seconds",
                        "pattern",
                        "score",
                        "reason",
                        "recent_accuracy",
                    ]
                )

    def write(self, sig: SignalState, recent_accuracy: float):
        if not self.enabled:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    datetime.utcnow().isoformat(),
                    sig.current_signal,
                    sig.current_confidence,
                    sig.next_signal,
                    sig.next_confidence,
                    sig.eta_seconds,
                    sig.pattern,
                    sig.score,
                    sig.reason,
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


def _draw_panel(out: np.ndarray, x0: int, y0: int, x1: int, y1: int, color=(25, 25, 28)):
    cv2.rectangle(out, (x0, y0), (x1, y1), color, -1)
    cv2.rectangle(out, (x0, y0), (x1, y1), (55, 55, 65), 1)


def draw_overlay(
    frame: np.ndarray,
    sig: SignalState,
    sr: Tuple[Optional[float], Optional[float]],
    active: bool,
    recent_acc: float,
    alert_threshold: int,
):
    support, resistance = sr
    out = frame.copy()
    h, w = out.shape[:2]

    panel_h = 150
    _draw_panel(out, 0, 0, w, panel_h, color=(13, 15, 19))

    status_col = (90, 220, 90) if active else (90, 90, 220)
    cv2.putText(out, f"Status: {'RUNNING' if active else 'PAUSED'}", (15, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_col, 2)

    # current signal card
    _draw_panel(out, 10, 34, w // 2 - 10, 106, color=(20, 24, 32))
    cur_col = (65, 220, 65) if sig.current_signal == "CALL" else (80, 130, 255)
    cv2.putText(out, "CURRENT SIGNAL", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(out, f"{sig.current_signal}  {sig.current_confidence:.1f}%", (20, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cur_col, 2)

    # next signal card
    _draw_panel(out, w // 2 + 10, 34, w - 10, 106, color=(20, 24, 32))
    nxt_col = (65, 220, 65) if sig.next_signal == "CALL" else (80, 130, 255)
    cv2.putText(out, "NEXT SIGNAL", (w // 2 + 20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(out, f"{sig.next_signal}  {sig.next_confidence:.1f}%  ETA:{sig.eta_seconds}s", (w // 2 + 20, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.7, nxt_col, 2)

    info = f"Pattern:{sig.pattern} | Score:{sig.score:.2f} | Acc:{recent_acc*100:.1f}% | Alert>={alert_threshold}%"
    cv2.putText(out, info, (15, 126), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (205, 205, 205), 1)
    cv2.putText(out, "Hotkeys: S pause  Q quit  L log  +/- alert", (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (170, 170, 170), 1)

    if support is not None:
        cv2.line(out, (0, int(support)), (w, int(support)), (0, 200, 210), 1)
    if resistance is not None:
        cv2.line(out, (0, int(resistance)), (w, int(resistance)), (210, 210, 0), 1)

    # right side confidence bar for NEXT signal
    bar_h = int((sig.next_confidence / 100.0) * (h - panel_h - 20))
    cv2.rectangle(out, (w - 22, h - 10 - bar_h), (w - 12, h - 10), nxt_col, -1)
    cv2.rectangle(out, (w - 22, panel_h + 10), (w - 12, h - 10), (80, 80, 80), 1)

    return out


def beep():
    try:
        import winsound

        winsound.Beep(1150, 150)
    except Exception:
        print("\a", end="")


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("Missing config.yaml. Copy config.example.yaml to config.yaml first.")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def main():
    cfg = load_config()
    web = QuotexWebApp(cfg)
    extractor = CandleExtractor(cfg)
    matcher = TemplateMatcher()
    model = HeavyLocalModel(cfg)
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
        sig = SignalState("WAIT", 50.0, "WAIT", 50.0, int(cfg["chart"]["timeframe_seconds"]), "NONE", 0.0, "paused")
        sr = (None, None)

        if active:
            candles = extractor.extract(chart)
            model.update_from_outcome(candles)
            pattern = PatternDetector.detect(candles)
            sr = support_resistance(candles, int(cfg["prediction"]["support_resistance_lookback"]))

            tpl_score = 0.0
            if candles:
                cx = int(np.clip(candles[-1].x, 8, chart.shape[1] - 8))
                tpl_score = matcher.match_score(chart[:, max(0, cx - 8) : min(chart.shape[1], cx + 8)])

            feats = FeatureEngineer.build(candles, pattern, sr[0], sr[1], tpl_score)
            sig = model.predict(candles, feats, pattern)

            recent_acc = model.get_recent_accuracy()
            logger.write(sig, recent_acc)

            now = int(time.time())
            if sig.next_confidence >= alert_threshold and now != last_alert:
                beep()
                last_alert = now
        else:
            recent_acc = model.get_recent_accuracy()

        shown = draw_overlay(chart, sig, sr, active, recent_acc, alert_threshold)
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
