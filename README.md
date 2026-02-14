# Qxbroker / Quotex CV Bot (Dual Signal + Heavy Local AI)

> ⚠️ Educational / paper-trading only.

This revised version now shows:
- **Current signal** (what it sees right now)
- **Next signal** (prediction for next candle)

It also upgrades the local model into a much heavier architecture with an optional **~5GB on-disk memory bank**.

## What changed

- Added dual signal outputs:
  - `CURRENT SIGNAL`
  - `NEXT SIGNAL` + ETA countdown
- Polished UI with card-style overlay, confidence bar, and cleaner status text.
- Added a much richer feature set (36 engineered features):
  - multi-horizon momentum, velocity
  - body/wick structure
  - EMA spreads, MACD, RSI, stochastic, CCI, ATR
  - volatility, trend slopes, Bollinger position
  - support/resistance distances
  - bullish ratio windows, template score, pattern score
- Added heavy local model stack:
  - linear head
  - deep nonlinear head
  - optional on-disk memory bank (`memmap`) targeting ~5GB
  - online adaptation from realized candle outcomes

## qxbroker security verification

If you see:
- "Performing security verification"
- "This website uses a security service..."

Complete verification manually in the opened browser window; the app waits for it. This bot does **not** bypass anti-bot checks.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configure

```bash
cp config.example.yaml config.yaml
```

Key settings:
- `model.enable_heavy_memory_bank: true`
- `model.target_size_gb: 5.0`
- `prediction.feature_weights` (36 values)
- chart color thresholds + timeframe

## Run

```bash
python quotex_cv_bot.py
```

Runtime:
1. Browser opens qxbroker.
2. Complete verification/login.
3. Press Enter in terminal.
4. Drag-select chart ROI once.
5. Bot starts dual-signal output with heavy local model.

## Hotkeys

- `S` pause/resume
- `L` logging on/off
- `+/-` alert threshold
- `Q` quit

## Notes on 5GB model

On first run with `enable_heavy_memory_bank: true`, the app creates a large local memmap file in `model_dir`. This can take time and disk space, but gives you a heavier local model footprint as requested.
