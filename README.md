# Quotex Screen-Driven Trading Bot

## Overview
This project implements a modular, asynchronous trading system for Quotex when no public API is available. It captures live chart pixels, reconstructs candles, computes indicators, generates hybrid rule+ML predictions, and optionally executes binary-option trades.

## Architecture
- `data_capture/`: low-latency screen capture via MSS + OpenCV
- `data_processing/`: candle extraction and OHLC approximation
- `indicators/`: vectorized technical indicators (EMA, SMA, RSI, MACD, BB, ATR, Stochastic, S/R, ADX)
- `ml_model/`: hybrid ML probability model (XGBoost/LightGBM fallback)
- `strategy/`: pattern engine + confidence aggregation
- `execution/`: risk filters and trade execution logging
- `gui/`: transparent always-on-top PySide overlay
- `core/`: async orchestration loop
- `utils/`: config persistence and logging

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

At startup the bot opens the Quotex page in your browser. Set capture region once in `config.json` (`runtime.region: [left, top, width, height]`) for stable low latency.

## Performance Targets
- Capture-to-prediction target: <150ms
- End-to-end target: <300ms
- Rolling buffer: default 500 candles
- GUI updates non-blocking via separate thread

## Logging
- `logs/app.log`: runtime logs/errors
- `logs/predictions.csv`: every prediction + latency
- `logs/trades.csv`: trade actions and stake sizing

## Debugging
Set `runtime.debug=true` in `config.json` for verbose logging.

## Auto-Trading Risk Controls
Configured in `config.json`:
- confidence threshold
- fixed capital percentage per trade
- optional martingale
- stop-loss streak limit
- max trades/hour

## Retraining Notes
The ML model is retrained continuously on rolling live features (`tail(800)` by default). You can tune:
- model hyperparameters in `ml_model/hybrid_model.py`
- fit frequency and data window in `core/orchestrator.py`

## Optional GPU Acceleration
- XGBoost GPU builds can be used by installing a CUDA-enabled package.
- For LightGBM GPU, compile/install with GPU support and set GPU params in the model config.

## Disclaimer
This software is for research/education. Binary options trading is high risk. You are solely responsible for financial outcomes and regulatory compliance.
