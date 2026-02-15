# Candlestick Vision Predictor (Production Desktop App)

A standalone **analysis-only** Python desktop application for real-time candlestick extraction and next-candle probability prediction.

## Safety Constraint

- No broker automation
- No clicks/order placement
- No process injection
- No external platform control
- Analysis-only workflow

## Architecture

- **Main thread:** PyQt6 GUI only
- **Thread 1:** `ScreenCaptureWorker` (`mss` ROI capture at 10–20 FPS)
- **Thread 2:** `CandleVisionWorker` (OpenCV candle detection + OHLC extraction)
- **Thread 3:** `InferenceWorker` (ensemble prediction)
- Bounded thread-safe queues between every stage
- Router/watchdog loop updates shared state and auto-restarts crashed workers

## Features

### 1) Screen Capture
- Interactive click-drag ROI selection
- 10–20 FPS target (default 15)
- Error propagation to GUI with red warning states
- Optimized capture path (single NumPy conversion, optional downscale)

### 2) Computer Vision Candle Extraction
- HSV color segmentation for bullish/bearish bodies
- Wick detection from mask extrema
- Bullish/bearish classification
- Approximate normalized OHLC extraction
- Rolling buffer of last 100 candles

### 3) Feature Engineering (vectorized)
- RSI(14)
- EMA(9, 21, 50)
- MACD + signal
- Bollinger Bands
- ATR(14)
- Candle pattern detection
- Trend slope
- Volatility regime

### 4) Model Ensemble
- Random Forest
- XGBoost (optional if installed)
- LSTM (TensorFlow optional)
- Weighted averaging for:
  - Bullish probability
  - Bearish probability
  - Confidence (agreement-based)

### 5) GUI (PyQt6 dark theme)
- Live reconstructed candles
- Prediction output and probability percentages
- Confidence meter
- FPS indicator
- Model status (`READY`, `TRAINING`, `ERROR`, `UNTRAINED`)
- Pipeline status (`LOADING`, `RUNNING`, `WARNING`, `ERROR`, `STOPPED`)
- Never-blank loading states

### 6) Training Mode
- Optional append of extracted rows to CSV
- Offline training from CSV
- Save/load model weights from `models/`

## Run

```bash
python -m trader_cv_app.main
```

## Notes

- CV detection is heuristic and depends on chart colors/theme.
- For best results, use a clean candlestick area with high contrast.
