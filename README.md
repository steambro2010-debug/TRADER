# Live Screen-Based AI Trading Signal System

This repository contains a modular Python starter implementation for a **screen-only** trading signal assistant.
It captures a chart region from your monitor, reconstructs candles visually, computes indicators, runs an ensemble model,
and displays directional signals (**BULLISH / BEARISH / NEUTRAL**) with confidence.

> It does **not** execute trades and does not rely on exchange APIs or WebSockets.

## Features

- Real-time screen capture using `mss` + OpenCV ROI selection
- Visual candle extraction from chart frames (CV-based baseline)
- Structured candle stream with OHLC + timestamp persistence
- Technical indicators: EMA(9/21/50), RSI(14), MACD(12/26/9), ATR(14), Bollinger Bands
- Ensemble prediction architecture:
  - Sequence model wrapper (PyTorch LSTM if available)
  - Tree model (XGBoost if available, otherwise sklearn fallback)
  - Weighted ensemble output
- Live threaded pipeline (capture + extraction + prediction + UI)
- Tkinter UI with:
  - Last extracted candles
  - Latest signals with confidence
  - Rolling accuracy over last N closed predictions
  - Prediction ON/OFF toggle
- Backtesting/logging utilities from persisted CSV files

## Project Structure

```text
src/trader_ai/
  capture.py           # Screen capture and region management
  candle_extractor.py  # CV extraction of candle candidates to OHLC
  indicators.py        # Indicator engine
  models.py            # Ensemble model abstractions
  pipeline.py          # Realtime threaded orchestrator
  data.py              # CSV persistence
  backtest.py          # Accuracy tracking and evaluation
  ui.py                # Tkinter dashboard
  config.py            # Runtime configuration dataclasses
  main.py              # Application entrypoint
  train.py             # Offline training entrypoint
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Live App

```bash
PYTHONPATH=src python -m trader_ai.main
```

At startup:
1. Press **s** on the capture window to select chart ROI.
2. Drag/select chart region and confirm.
3. The app starts extracting candles and generating signals on candle-close events.

## Train Models

You can train from historical structured candles CSV:

```bash
PYTHONPATH=src python -m trader_ai.train --input data/candles.csv --model-dir models
```

CSV expected columns:
- `timestamp`
- `open`, `high`, `low`, `close`

## Notes / Limitations

- Visual OHLC extraction quality depends heavily on chart theme and scaling.
- Baseline extractor assumes a candlestick chart with distinct bullish/bearish body colors.
- Price mapping is pixel-derived unless you calibrate vertical bounds in config.
- No fixed performance claims are made; all accuracy is measured live.

## Milestones Covered

- **Milestone 1:** capture + visual candle extraction + structured candle persistence
- **Milestone 2:** real-time indicator generation
- **Milestone 3:** trainable ensemble model interfaces
- **Milestone 4:** live inference pipeline
- **Milestone 5:** UI + rolling accuracy/backtest-ready logs
