# QuoTex Real-Time Chart Signal Bot — Technical Requirements

## 1) Scope and Objective
Build a decision-support AI bot that observes chart visuals from a live PC screenshare, infers short-horizon market direction, and outputs actionable signals:
- **UP** (buy/call)
- **DOWN** (sell/put)
- **NO-TRADE** (insufficient edge)

> Important: Treat this as a **decision-support system**, not an autonomous guaranteed-profit system. In live markets, an 85–90% stable hit rate is uncommon and should be treated as a stretch target under narrow, controlled market regimes.

---

## 2) Non-Functional Requirements
- **Latency budget**: end-to-end signal delay ≤ 300–700 ms (capture -> preprocess -> inference -> signal).
- **Availability**: 99% uptime during trading sessions.
- **Observability**: full logging of inputs, model outputs, confidence, and realized outcomes.
- **Risk controls**: hard daily loss limit, max consecutive losses, and no-trade zones during high uncertainty.
- **Security**: encrypted local storage for session logs; API secrets in environment vault.

---

## 3) System Architecture

## 3.1 Modules
1. **Screen Capture Layer**
   - Captures ROI (region of interest) containing candles, indicators, and timeframe.
   - 5–15 FPS for analysis (not full video frame rate).

2. **Chart Understanding Layer**
   - OCR for symbol/timeframe/price labels.
   - CV extraction of candle structures, trend lines, support/resistance, and overlay indicators.
   - Optional direct OHLC reconstruction from chart pixels.

3. **Feature Engineering Layer**
   - Price-action features (candle body/wick ratios, momentum, breakouts).
   - Indicator features (RSI/MACD/EMA slope if visible).
   - Context features (volatility regime, time-of-day, spread/proxy uncertainty).

4. **Prediction Layer**
   - Ensemble classifier outputs `P(UP)`, `P(DOWN)`, and confidence.
   - Calibrated probability + uncertainty estimate.

5. **Execution/Signal Layer**
   - Emits `UP`, `DOWN`, or `NO-TRADE` based on decision policy.
   - Integrates with QuoTex interaction channel (API if available; UI automation fallback only if compliant with platform terms).

6. **Evaluation & Retraining Layer**
   - Tracks live performance by instrument, timeframe, and regime.
   - Scheduled retraining and drift detection.

---

## 4) Data Inputs Required

## 4.1 Real-Time Inputs
- **Primary**: Screen frames from chart ROI (candles + indicators + timeframe).
- **Metadata from OCR**:
  - Instrument name (e.g., EUR/USD)
  - Chart timeframe (e.g., 1m/5m)
  - Current price marker
- **Session context**:
  - Timestamp (UTC)
  - Trading session (Asia/London/NY)
  - Optional economic-news risk flag

## 4.2 Training Inputs
- Historical frame sequences + aligned outcomes over fixed horizons (e.g., +30s, +60s, +120s).
- Labels:
  - `UP` if close at horizon > entry + threshold
  - `DOWN` if close at horizon < entry - threshold
  - `NO-TRADE` / neutral otherwise
- At least 50k–200k labeled windows across multiple regimes recommended.

## 4.3 Optional Inputs (Improve Reliability)
- Raw broker feed OHLC if obtainable legally.
- Synthetic chart augmentations (brightness/noise/resolution/layout changes).
- Volatility and spread proxies from visible chart behavior.

---

## 5) Algorithms for Chart Analysis

## 5.1 Computer Vision + Sequence Modeling (Recommended)
1. **Frame preprocessing**
   - ROI crop, denoise, normalize colors, deskew.
   - Candle segmentation using color masks + contour extraction.

2. **Visual encoding**
   - CNN/ViT encoder (EfficientNet, ConvNeXt, or ViT-small) per frame.

3. **Temporal modeling**
   - TCN/LSTM/Transformer on sequence of embeddings (e.g., 20–60 frames).

4. **Output head**
   - Multi-class classifier: `UP`, `DOWN`, `NO-TRADE`.
   - Predictive uncertainty via temperature scaling / MC dropout.

## 5.2 Hybrid Rule + ML Ensemble (Practical)
- **Rule engine** for high-precision patterns:
  - Trend continuation (EMA alignment + pullback)
  - Breakout + retest
  - Reversal at strong support/resistance with confirmation candle
- **ML model** validates/filters rule signals.
- Final signal only when rule and ML agree or probability exceeds threshold.

## 5.3 Baseline Features (If CV is delayed)
Derive pseudo-OHLC from chart pixels and train:
- XGBoost/LightGBM on technical features
- Sequence features from last N candles
- This gives a fast MVP for benchmarking.

---

## 6) Decision Policy (Signal Generation)
Define thresholds:
- `UP` if `P(UP) >= 0.62` and `P(UP)-P(DOWN) >= margin`
- `DOWN` if `P(DOWN) >= 0.62` and `P(DOWN)-P(UP) >= margin`
- Else `NO-TRADE`

Add gates:
- Min confidence + low uncertainty.
- Block trading during detected news spikes or abnormal volatility.
- Cooldown after loss streak (e.g., 3 losses).

---

## 7) Achieving 85–90%: Realistic Path

## 7.1 Accuracy Definition (Must be explicit)
Use **precision on traded signals** (excluding no-trade), not raw accuracy across all frames.
- Example KPI stack:
  - Precision on UP/DOWN trades
  - Trade frequency
  - Expectancy (avg win - avg loss)
  - Max drawdown

## 7.2 Steps to approach high precision
1. **Trade less, trade better**: aggressive no-trade filter.
2. **Regime segmentation**: separate models for trending vs ranging markets.
3. **Instrument specialization**: one model per symbol/timeframe pair.
4. **Probability calibration**: isotonic/Platt scaling.
5. **Walk-forward validation**: avoid random split leakage.
6. **Hard risk limits**: protect against sudden regime shifts.

## 7.3 Reality check
- 85–90% can appear in constrained setups (specific symbol/time window/pattern).
- Sustained 85–90% across all market conditions is unlikely; optimize for **risk-adjusted return**, not hit rate alone.

---

## 8) Integration with QuoTex

## 8.1 Preferred Integration Order
1. **Official API/WebSocket** (if available and permitted):
   - Auth
   - Market state pull
   - Order placement endpoint
2. **Semi-automated mode**:
   - Bot posts signal to desktop/mobile alert channel (Telegram/Discord/local overlay).
   - Human confirms execution.
3. **UI automation fallback** (Selenium/Playwright/desktop automation):
   - Use only if compliant with QuoTex ToS and jurisdiction rules.

## 8.2 Integration Requirements
- `BrokerAdapter` interface:
  - `connect()`
  - `get_balance()`
  - `place_order(direction, amount, expiry)`
  - `get_order_result(order_id)`
- Retries, idempotency keys, and order-state reconciliation.
- Circuit breaker when API/ui interaction fails repeatedly.

---

## 9) Suggested Tech Stack
- **Language**: Python 3.11+
- **CV/ML**: OpenCV, PyTorch, timm, scikit-learn, LightGBM
- **OCR**: EasyOCR or Tesseract
- **Realtime**: asyncio, FastAPI (signal service), Redis (queue/cache)
- **Storage**: PostgreSQL (trades/results), MinIO/S3 (frame sequences)
- **Monitoring**: Prometheus + Grafana + structured logs

---

## 10) Training and Validation Pipeline
1. Data collection daemon records frame windows + outcomes.
2. Labeling job assigns UP/DOWN/NO-TRADE by fixed horizon logic.
3. Feature/image pipeline builds train/val/test by time splits.
4. Train model ensemble + calibrate probabilities.
5. Backtest with slippage/latency simulation.
6. Paper-trade forward test (2–4 weeks minimum).
7. Deploy with canary mode and kill switch.

---

## 11) Minimum Viable Milestones
- **M1 (1–2 weeks)**: capture + OCR + signal dashboard (no execution).
- **M2 (2–4 weeks)**: baseline model + paper trading.
- **M3 (4–6 weeks)**: hybrid ensemble + risk engine + broker adapter.
- **M4 (ongoing)**: drift monitoring, retraining, and per-regime optimization.

---

## 12) Core Acceptance Criteria
- Signal latency median < 500 ms.
- Paper-trading precision target >= 70% initial, improving with filters.
- Stable operations over 2+ weeks with no critical failures.
- Full audit trail for every signal and result.

---

## 13) Implementation Starter Blueprint
- Services:
  - `capture-service`
  - `feature-service`
  - `inference-service`
  - `risk-service`
  - `broker-adapter-service`
  - `monitoring-service`
- Message flow:
  1. Capture -> frame sequence
  2. Feature extraction -> vector/tensor
  3. Inference -> class probabilities
  4. Risk policy -> signal decision
  5. Broker adapter / alert dispatch

This structure is robust, testable, and production-friendly for iterative improvement.
