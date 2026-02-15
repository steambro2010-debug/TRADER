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
run_live.py            # Launch live app (no PYTHONPATH needed)
run_train.py           # Launch trainer (no PYTHONPATH needed)
```

## Installation

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If script execution is blocked in PowerShell, run once in that terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Linux/macOS (bash/zsh)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run Live App

### Recommended (cross-platform, no `PYTHONPATH` needed)

```bash
python run_live.py
```

### Alternative module form

- **PowerShell**

```powershell
$env:PYTHONPATH = "src"
python -m trader_ai.main
```

- **Linux/macOS**

```bash
PYTHONPATH=src python -m trader_ai.main
```

At startup:
1. Select chart ROI in the OpenCV selector and confirm.
2. The app starts extracting candles and generating signals on candle-close events.

## Train Models

### Recommended

```bash
python run_train.py --input data/candles.csv --model-dir models
```

### Alternative module form

- **PowerShell**

```powershell
$env:PYTHONPATH = "src"
python -m trader_ai.train --input data/candles.csv --model-dir models
```

- **Linux/macOS**

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
