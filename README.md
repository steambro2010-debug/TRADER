# Quotex Browser-Embedded Trading Engine

## What Changed
This project no longer uses screen scraping, OpenCV, MSS, or pixel-based candle reconstruction.
It embeds Chromium via PyQt6 WebEngine, captures structured network/state data, and processes it in Python.

## Browser Stability (Chrome-like behavior)
- Uses a **persistent** `QWebEngineProfile` with dedicated storage/cache paths.
- Uses a realistic Chrome user agent string.
- Enables persistent cookies, local storage, cache, WebGL and GPU-accelerated canvas.
- Delays WebSocket hook injection (`hook_injection_delay_seconds`, default 8s) to avoid early-page JS instability.
- Logs JavaScript console messages for CSP/auth/WebSocket debugging.
- Watchdog reloads only after confirmed WS activity followed by repeated stale intervals (prevents refresh loops before login).

## Architecture
- `data_capture/browser_engine.py` — embedded Chromium + persistent profile + delayed JS injection + WebSocket hooks
- `data_processing/candle_reconstructor.py` — structured candle parser + rolling 1200-candle buffer
- `indicators/technical.py` — vectorized indicator stack (EMA/SMA/RSI/MACD/BB/ATR/Stochastic/ADX/S/R)
- `ml_model/hybrid_model.py` — calibrated XGBoost/LightGBM model fallback
- `strategy/signal_generator.py` — direction + confidence generation grounded in model probabilities
- `execution/trade_executor.py` — DOM click execution with risk constraints and fail-safe checks
- `gui/main_window.py` — analytics panel with probability bar, threshold slider, trade log, diagnostics
- `core/orchestrator.py` — threaded packet ingestion, ML inference, guarded watchdog reload, graceful shutdown

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Runtime Flow
1. Launch embedded Quotex browser.
2. User logs in manually.
3. Bridge initializes; hook is injected after delay.
4. WebSocket packets are bridged to Python via `QWebChannel`.
5. Candle objects are parsed and buffered (1000+ candles).
6. Indicators + calibrated ML probabilities generate UP/DOWN predictions.
7. Optional auto-trade uses DOM click execution.


## AI Diagnostics & Tracing
- Pipeline stages now emit explicit traces such as:
  - `[WEBSOCKET_DATA_RECEIVE] SUCCESS`
  - `[CANDLE_PARSED] SUCCESS`
  - `[INDICATORS_CALCULATED] SUCCESS`
  - `[FEATURE_VECTOR_BUILT] SUCCESS`
  - `[MODEL_INFERENCE_CALLED] SUCCESS`
  - `[PREDICTION_RETURNED] SUCCESS`
  - `[GUI_UPDATED] SUCCESS`
- A forced test prediction loop runs every `test_prediction_interval_seconds` (default 5s).
- Buffer guards show `Collecting data...` until `min_candles_for_prediction` is reached.
- Set `force_test_prediction_output=true` to force `{up: 65%, down: 35%}` wiring checks.
- Use the **Force Predict** button to run prediction immediately and bypass minimum-candle guard.
- The candle parser deduplicates by timestamp and updates the current open candle in-place (no buffer reset on ticks).


## UI Dashboard
- Modern dark trading-intelligence layout with card-based sections and gradient styling.
- Dominant AI Status card: Direction, Confidence, Status, Model mode.
- Animated UP/DOWN probability bars with green/red visual encoding.
- Collapsible indicator chip row: RSI, MACD histogram, ADX, volatility, trend bias.
- Scrollable trade log with conditional row coloring (win/loss).
- Health header: CPU, FPS, latency, and candle buffer size.
- Dynamic statuses:
  - `Collecting data: N / min candles`
  - `Analyzing…`
  - `AI Ready` / `Weak Signal`

## Config Notes
`config.json` runtime keys include:
- `browser_profile_path`
- `browser_cache_path`
- `browser_user_agent`
- `hook_injection_delay_seconds`
- `websocket_reconnect_seconds`

## Disclaimer
Trading binary options is high risk. This software is for research/education only. You are fully responsible for financial and legal outcomes.
